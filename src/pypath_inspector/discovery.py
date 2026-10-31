"""Discovery of Python interpreters via PATH, the py launcher and uv.

Interpreters are collected from three sources and deduplicated by their
real (symlink-resolved) path:

1. PATH scan for ``python``, ``python3`` and ``pythonw`` (plus versioned
   ``python3.x`` names on POSIX).
2. The Windows ``py`` launcher (``py -0p`` / ``py --list-paths``).
3. ``uv python list --only-installed`` when uv is available.

Discovery never claims to be exhaustive: interpreters that are installed
but not reachable through any of these mechanisms cannot be reported. The
returned notes make that boundary explicit.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from .models import Interpreter, InterpreterProbe
from .probing import Runner, error_kind, probe_interpreter
from .resolution import find_on_path

DISCOVERY_NAMES = ("python", "python3", "pythonw")

_PY_TAG_LINE_RE = re.compile(r"^\s*-V:([^\s*]+)(\s*\*)?\s+(\S.*?)\s*$")
_UV_LINE_RE = re.compile(r"^(\S+)\s{2,}(.+)$")
_UV_VERSION_RE = re.compile(r"(\d+\.\d+(?:\.\d+)?)")
_GENERIC_PATH_RE = re.compile(r'(?:[A-Za-z]:[\\/]|/)[^\s"\']+')
_POSIX_VERSIONED_NAME_RE = re.compile(r"python3\.\d+[a-z]?")


@dataclass(frozen=True)
class DiscoveryResult:
    """Outcome of interpreter discovery.

    Attributes:
        interpreters: Deduplicated interpreters, ordered by path.
        notes: Non-fatal caveats (missing listed paths, failed managers).
        probes: Probe results keyed by normalised real path, reused by the
            diagnostics layer so no interpreter is executed twice.
    """

    interpreters: tuple[Interpreter, ...] = ()
    notes: tuple[str, ...] = ()
    probes: dict[str, InterpreterProbe] = field(default_factory=dict)


class _Accumulator:
    """Mutable builder for one deduplicated interpreter entry."""

    def __init__(self, path: str, real_path: str, source: str, alias: str | None, version: str | None) -> None:
        self.path = path
        self.real_path = real_path
        self.version = version
        self.sources: list[str] = [source]
        self.aliases: list[str] = [alias] if alias else []

    def add(self, source: str, alias: str | None, version: str | None) -> None:
        if source not in self.sources:
            self.sources.append(source)
        if alias and alias not in self.aliases:
            self.aliases.append(alias)
        if self.version is None and version:
            self.version = version

    def build(self) -> Interpreter:
        return Interpreter(
            path=self.path,
            real_path=self.real_path,
            version=self.version,
            sources=tuple(self.sources),
            aliases=tuple(self.aliases),
        )


def _real_key(path: str) -> str:
    """Normalised real path used as the deduplication key."""
    return os.path.normcase(os.path.realpath(path))


def discover_interpreters(
    runner: Runner,
    path_var: str,
    pathext: list[str] | None = None,
    py_path: str | None = None,
    uv_path: str | None = None,
    versioned_glob: bool | None = None,
) -> DiscoveryResult:
    """Discover Python interpreters on this machine.

    Args:
        runner: Subprocess runner used for the py launcher and uv.
        path_var: The PATH variable content to scan.
        pathext: PATHEXT extensions, ``None`` for the platform default.
        py_path: Resolved path of the ``py`` launcher, or ``None`` to skip it.
        uv_path: Resolved path of ``uv``, or ``None`` to skip it.
        versioned_glob: Whether to glob for ``python3.x`` names in PATH
            directories; ``None`` enables it on POSIX only.

    Returns:
        A :class:`DiscoveryResult`; never raises.
    """
    if pathext is None and os.name == "nt":
        from .resolution import default_pathext

        pathext = default_pathext()
    if versioned_glob is None:
        versioned_glob = os.name == "posix"

    found: dict[str, _Accumulator] = {}
    notes: list[str] = []
    probes: dict[str, InterpreterProbe] = {}

    for name in DISCOVERY_NAMES:
        for match in find_on_path(name, path_var, pathext):
            _add(found, match.path, "PATH", alias=name, version=None)

    if versioned_glob:
        for directory in (part for part in path_var.split(os.pathsep) if part):
            try:
                candidates = os.listdir(directory)
            except OSError:
                continue
            for filename in candidates:
                if not _POSIX_VERSIONED_NAME_RE.fullmatch(filename):
                    continue
                full = os.path.join(directory, filename)
                if os.path.isfile(full) and os.access(full, os.X_OK):
                    _add(found, full, "PATH", alias=filename, version=None)

    if py_path:
        result = runner([py_path, "-0p"])
        if result.ok:
            for line in result.stdout.splitlines():
                _consume_manager_line(line, found, notes, "py-launcher", _parse_py_line)
        else:
            notes.append(f"py-launcher query failed ({_failure(result)}).")

    if uv_path:
        result = runner([uv_path, "python", "list", "--only-installed"])
        if result.ok:
            for line in result.stdout.splitlines():
                _consume_manager_line(line, found, notes, "uv", _parse_uv_line)
        else:
            notes.append(f"uv query failed ({_failure(result)}).")

    interpreters = _fill_versions(found, runner, probes)
    return DiscoveryResult(
        interpreters=interpreters,
        notes=tuple(notes),
        probes=probes,
    )


def _failure(result) -> str:
    """Describe a failed manager query for a discovery note."""
    return result.error if result.error else f"exit code {result.returncode}"


def _add(
    found: dict[str, _Accumulator],
    path: str,
    source: str,
    alias: str | None,
    version: str | None,
) -> None:
    """Add or merge one interpreter entry into the discovery accumulator."""
    key = _real_key(path)
    existing = found.get(key)
    if existing is None:
        found[key] = _Accumulator(path, os.path.realpath(path), source, alias, version)
    else:
        existing.add(source, alias, version)


def _consume_manager_line(line, found, notes, manager, parser) -> None:
    """Parse one output line from py/uv, noting missing listed paths.

    Lines that the structured parser cannot handle (for example output of
    newer launcher versions) fall back to extracting any existing absolute
    path mentioned in the line.
    """
    parsed = parser(line)
    if parsed is None:
        generic = _extract_existing_path(line)
        if generic is not None:
            _add(found, generic, manager, alias=None, version=None)
        return
    path, version = parsed
    if not os.path.isfile(path):
        notes.append(f"{manager} lists an interpreter path that does not exist: {path}")
        return
    _add(found, path, manager, alias=None, version=version)


def _parse_py_line(line: str) -> tuple[str, str | None] | None:
    """Parse one ``py -0p`` line into (path, version tag)."""
    match = _PY_TAG_LINE_RE.match(line)
    if match:
        return match.group(3), match.group(1)
    return None


def _parse_uv_line(line: str) -> tuple[str, str | None] | None:
    """Parse one ``uv python list`` line into (path, version)."""
    match = _UV_LINE_RE.match(line.strip())
    if not match:
        return None
    name, path = match.group(1), match.group(2).strip()
    version = _UV_VERSION_RE.search(name)
    return path, version.group(1) if version else None


def _extract_existing_path(line: str) -> str | None:
    """Extract the first existing absolute path mentioned in *line*."""
    for match in _GENERIC_PATH_RE.finditer(line):
        candidate = match.group(0).strip('"')
        if os.path.isfile(candidate):
            return candidate
    return None


def _fill_versions(
    found: dict[str, _Accumulator],
    runner: Runner,
    probes: dict[str, InterpreterProbe],
) -> tuple[Interpreter, ...]:
    """Probe PATH-sourced interpreters so the report can show versions.

    Interpreters whose file name suggests a GUI launcher (``pythonw``)
    are not executed; their version is copied from a sibling interpreter
    in the same directory when one is known.
    """
    built: list[Interpreter] = []
    for key, accumulator in found.items():
        if "PATH" in accumulator.sources and not _is_gui_name(accumulator.path):
            probe = probes.get(key) or probe_interpreter(accumulator.path, runner)
            probes[key] = probe
            if probe.ok and probe.version:
                accumulator.version = probe.version
        built.append(accumulator.build())

    by_directory: dict[str, str] = {}
    for interpreter in built:
        if interpreter.version:
            by_directory.setdefault(os.path.dirname(interpreter.real_path), interpreter.version)
    filled = []
    for interpreter in built:
        if interpreter.version is None:
            sibling = by_directory.get(os.path.dirname(interpreter.real_path))
            if sibling is not None:
                interpreter = Interpreter(
                    path=interpreter.path,
                    real_path=interpreter.real_path,
                    version=sibling,
                    sources=interpreter.sources,
                    aliases=interpreter.aliases,
                )
        filled.append(interpreter)
    return tuple(sorted(filled, key=lambda item: os.path.normcase(item.path)))


def _is_gui_name(path: str) -> bool:
    """Whether the file name suggests a GUI launcher (never executed)."""
    return os.path.basename(path).lower().startswith("pythonw")
