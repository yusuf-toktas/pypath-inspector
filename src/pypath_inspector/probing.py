"""Subprocess probing with strict timeouts and graceful failure handling.

Every external command executed by PyPath Inspector goes through a
:class:`Runner`. Runners never raise: they always return a
:class:`CommandResult` describing success, non-zero exit, timeout,
missing executable, permission error or operating-system error. This keeps
the diagnostic layers free of scattered ``try``/``except`` blocks and makes
the whole pipeline trivially testable with fake runners.
"""

from __future__ import annotations

import json
import locale
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Callable, Sequence

from .models import InterpreterProbe, PipVersionInfo

DEFAULT_TIMEOUT = 15.0

_DETAIL_LIMIT = 300

_PROBE_CODE = (
    "import json, platform, sys; "
    "print(json.dumps({"
    "'version': platform.python_version(), "
    "'executable': sys.executable, "
    "'base_executable': getattr(sys, '_base_executable', None), "
    "'prefix': sys.prefix, "
    "'base_prefix': sys.base_prefix}))"
)

_PIP_VERSION_RE = re.compile(r"pip\s+(\S+)\s+from\s+(.+?)\s+\(python\s+([^)]+)\)")
_PYTHON_VERSION_RE = re.compile(r"Python\s+([0-9][0-9A-Za-z.+\-]*)")

_STORE_STUB_MARKERS = (
    "python was not found",
    "microsoft store",
    "app execution aliases",
)


@dataclass(frozen=True)
class CommandResult:
    """Outcome of one external command execution.

    Attributes:
        argv: The command that was executed.
        returncode: Process exit code, or ``None`` when it never completed.
        stdout: Decoded standard output.
        stderr: Decoded standard error.
        timed_out: Whether the command exceeded the configured timeout.
        error: ``None`` on clean execution, otherwise a machine-readable
            failure kind: ``not-found``, ``permission-denied``,
            ``timeout``, ``empty-command`` or ``os-error: ...``.
    """

    argv: tuple[str, ...]
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool
    error: str | None

    @property
    def ok(self) -> bool:
        """Whether the command completed successfully."""
        return self.error is None and self.returncode == 0


Runner = Callable[[Sequence[str]], CommandResult]


def make_runner(timeout: float = DEFAULT_TIMEOUT) -> Runner:
    """Create a :class:`Runner` that executes commands with a hard timeout."""

    def run(argv: Sequence[str]) -> CommandResult:
        args = [str(part) for part in argv]
        if not args:
            return CommandResult((), None, "", "", False, "empty-command")
        try:
            completed = subprocess.run(args, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return CommandResult(tuple(args), None, "", "", True, "timeout")
        except FileNotFoundError:
            return CommandResult(tuple(args), None, "", "", False, "not-found")
        except PermissionError:
            return CommandResult(tuple(args), None, "", "", False, "permission-denied")
        except OSError as exc:
            return CommandResult(tuple(args), None, "", "", False, f"os-error: {exc}")
        return CommandResult(
            tuple(args),
            completed.returncode,
            _decode(completed.stdout),
            _decode(completed.stderr),
            False,
            None,
        )

    return run


def _decode(data: bytes) -> str:
    """Decode subprocess output, falling back to the locale encoding."""
    if not data:
        return ""
    for encoding in ("utf-8", _preferred_encoding()):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


def _preferred_encoding() -> str:
    try:
        return locale.getencoding() or "utf-8"
    except AttributeError:
        return locale.getpreferredencoding(False) or "utf-8"


def error_kind(result: CommandResult) -> str:
    """Return a machine-readable failure kind for a non-ok result."""
    if result.error is not None:
        return result.error
    if result.returncode is not None and result.returncode != 0:
        return f"exit-{result.returncode}"
    return "bad-output"


def _detail(*chunks: str) -> str:
    """Join output chunks into a truncated, single-line detail string."""
    text = " ".join(chunk.strip() for chunk in chunks if chunk and chunk.strip())
    if len(text) > _DETAIL_LIMIT:
        text = text[: _DETAIL_LIMIT - 3] + "..."
    return text


def looks_like_store_stub(text: str) -> bool:
    """Whether *text* matches the Microsoft Store alias stub message."""
    lowered = text.lower()
    return any(marker in lowered for marker in _STORE_STUB_MARKERS)


def is_windowsapps_path(path: str) -> bool:
    """Whether *path* lives in the Windows ``WindowsApps`` alias directory."""
    lowered = path.replace("/", "\\").lower()
    return "\\microsoft\\windowsapps\\" in lowered or lowered.endswith("\\microsoft\\windowsapps")


def probe_interpreter(executable: str, runner: Runner) -> InterpreterProbe:
    """Execute *executable* to learn its version and environment layout.

    The interpreter is queried exactly the way a user would experience it
    (no isolated mode), so problems caused by ``PYTHONHOME`` or similar
    variables remain visible. A ``--version`` fallback covers interpreters
    that cannot run the JSON snippet.
    """
    result = runner([executable, "-c", _PROBE_CODE])
    if result.ok:
        try:
            payload = json.loads(result.stdout.strip().splitlines()[-1])
            return InterpreterProbe(
                executable=executable,
                ok=True,
                version=str(payload.get("version")) if payload.get("version") else None,
                sys_executable=payload.get("executable"),
                base_executable=payload.get("base_executable"),
                prefix=payload.get("prefix"),
                base_prefix=payload.get("base_prefix"),
                is_venv=(
                    payload.get("prefix") != payload.get("base_prefix")
                    if payload.get("prefix") and payload.get("base_prefix")
                    else None
                ),
            )
        except (ValueError, IndexError, TypeError):
            pass
    fallback = runner([executable, "--version"])
    version = None
    if fallback.ok or (fallback.returncode not in (None, 0) and not fallback.error):
        match = _PYTHON_VERSION_RE.search(fallback.stdout) or _PYTHON_VERSION_RE.search(fallback.stderr)
        if match:
            version = match.group(1)
    if version is not None:
        return InterpreterProbe(
            executable=executable,
            ok=True,
            version=version,
            error_kind=None,
        )
    failed = result if not result.ok else fallback
    detail = _detail(failed.stdout, failed.stderr)
    store_stub = (not result.ok) and (
        looks_like_store_stub(result.stdout + result.stderr) or is_windowsapps_path(executable)
    )
    return InterpreterProbe(
        executable=executable,
        ok=False,
        error_kind=error_kind(failed),
        error_detail=detail or None,
        store_stub=store_stub,
    )


def parse_pip_version(text: str) -> tuple[str, str, str] | None:
    """Parse ``pip --version`` output into (pip, install path, python)."""
    match = _PIP_VERSION_RE.search(text)
    if not match:
        return None
    return match.group(1), match.group(2), match.group(3)


def probe_pip(
    argv: Sequence[str],
    origin: str,
    runner: Runner,
    resolved_path: str | None = None,
) -> PipVersionInfo:
    """Run a pip version command and parse the result."""
    command = " ".join(str(part) for part in argv)
    result = runner(argv)
    parsed = parse_pip_version(result.stdout) if result.ok else None
    if parsed is not None:
        pip_version, install_path, python_version = parsed
        return PipVersionInfo(
            origin=origin,
            command=command,
            ok=True,
            pip_version=pip_version,
            python_version=python_version,
            install_path=install_path,
            resolved_path=resolved_path,
        )
    return PipVersionInfo(
        origin=origin,
        command=command,
        ok=False,
        resolved_path=resolved_path,
        error_kind=error_kind(result),
        error_detail=_detail(result.stdout, result.stderr) or None,
    )


def major_minor(version: str | None) -> str | None:
    """Reduce a version string to its ``major.minor`` prefix."""
    if not version:
        return None
    match = re.match(r"(\d+)\.(\d+)", version)
    if not match:
        return None
    return f"{match.group(1)}.{match.group(2)}"


def is_within_path(child: str, parent: str) -> bool:
    """Whether *child* is equal to or located underneath *parent*."""
    child_n = os.path.normcase(os.path.normpath(os.path.abspath(child)))
    parent_n = os.path.normcase(os.path.normpath(os.path.abspath(parent)))
    if not child_n or not parent_n:
        return False
    if child_n == parent_n:
        return True
    return child_n.startswith(parent_n.rstrip("\\/") + os.path.normcase(os.sep))
