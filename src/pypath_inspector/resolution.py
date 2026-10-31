"""Command resolution against PATH, including duplicate entry analysis.

The resolution logic mirrors ``shutil.which`` semantics but collects *all*
matches across every PATH entry, which makes it possible to report which
executable wins, which are shadowed and where duplicate PATH entries exist.
"""

from __future__ import annotations

import os
import re
from collections import defaultdict

from .models import (
    CommandMatch,
    CommandResolution,
    DuplicateGroup,
    PathAnalysis,
    PathEntryInfo,
)

COMMAND_NAMES = ("python", "python3", "pythonw", "pip", "pip3", "py", "uv")

_WINDOWS_PATHEXT_DEFAULT = ".COM;.EXE;.BAT;.CMD;.VBS;.VBE;.JS;.JSE;.WSF;.WSH;.MSC"

_POSIX_VERSIONED_NAME_RE = re.compile(r"python3\.\d+[a-z]?")

_SCRIPT_EXTENSIONS = (".bat", ".cmd", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh")


def default_pathext() -> list[str] | None:
    """Return the PATHEXT extension list on Windows, ``None`` elsewhere."""
    if os.name != "nt":
        return None
    raw = os.environ.get("PATHEXT", _WINDOWS_PATHEXT_DEFAULT)
    return [ext for ext in raw.split(os.pathsep) if ext]


def candidate_names(name: str, pathext: list[str] | None) -> list[str]:
    """Expand a command name into the file names PATH resolution considers.

    When *pathext* is ``None`` (POSIX behaviour) only the bare name is
    considered. On Windows the name is combined with every PATHEXT
    extension unless it already carries one.
    """
    if pathext is None:
        return [name]
    lowered = name.lower()
    if any(lowered.endswith(ext.lower()) for ext in pathext if ext):
        return [name]
    return [name + ext for ext in pathext if ext] or [name]


def find_on_path(
    name: str,
    path_var: str,
    pathext: list[str] | None = None,
) -> list[CommandMatch]:
    """Return every executable PATH resolution considers for *name*.

    Matches are returned in PATH order; within one PATH entry only the
    first candidate (by PATHEXT order) is kept, matching the behaviour of
    ``shutil.which``. Empty PATH entries are searched as the current
    directory, exactly like the operating system does. Matched paths use
    the file's on-disk name so reports read naturally.
    """
    matches: list[CommandMatch] = []
    for index, directory in enumerate(path_var.split(os.pathsep)):
        for candidate in candidate_names(name, pathext):
            if directory:
                full = os.path.join(directory, candidate)
            else:
                full = candidate
            if os.path.isfile(full) and os.access(full, os.X_OK):
                true_name = _on_disk_name(directory, candidate)
                matches.append(
                    CommandMatch(
                        path=os.path.join(directory, true_name) if directory else true_name,
                        directory=directory,
                        path_index=index,
                    )
                )
                break
    return matches


def _on_disk_name(directory: str, candidate: str) -> str:
    """Return the actual on-disk spelling of *candidate* when possible."""
    try:
        for entry in os.listdir(directory or "."):
            if entry.lower() == candidate.lower():
                return entry
    except OSError:
        pass
    return candidate


def resolve_commands(
    names: tuple[str, ...] = COMMAND_NAMES,
    path_var: str | None = None,
    pathext: list[str] | None = None,
) -> tuple[CommandResolution, ...]:
    """Resolve every command name in *names* against PATH.

    ``pathext`` follows the same convention as :func:`find_on_path`:
    ``None`` selects the platform default, an explicit list (possibly
    empty) overrides it for deterministic testing.
    """
    if path_var is None:
        path_var = os.environ.get("PATH", "")
    if pathext is None:
        pathext = default_pathext()
    resolutions = []
    for name in names:
        matches = find_on_path(name, path_var, pathext)
        resolved = matches[0].path if matches else None
        resolutions.append(CommandResolution(name=name, resolved=resolved, matches=tuple(matches)))
    return tuple(resolutions)


def normalize_entry(entry: str) -> str:
    """Normalise a PATH entry for duplicate comparison."""
    stripped = entry.strip()
    if not stripped:
        return ""
    return os.path.normcase(os.path.normpath(stripped))


def analyze_path(path_var: str) -> PathAnalysis:
    """Analyse PATH for empty, missing and duplicate entries.

    Comparison is case-insensitive on Windows (via ``os.path.normcase``),
    so ``C:\\Python`` and ``c:\\python\\`` are recognised as duplicates.
    """
    entries: list[PathEntryInfo] = []
    for index, raw in enumerate(path_var.split(os.pathsep)):
        normalized = normalize_entry(raw)
        is_empty = normalized == ""
        exists = (not is_empty) and os.path.isdir(raw.strip().strip('"'))
        entries.append(
            PathEntryInfo(index=index, raw=raw, normalized=normalized, exists=exists, is_empty=is_empty)
        )

    groups: dict[str, list[PathEntryInfo]] = defaultdict(list)
    for entry in entries:
        if not entry.is_empty:
            groups[entry.normalized].append(entry)

    duplicate_groups: list[DuplicateGroup] = []
    for normalized, group in groups.items():
        if len(group) > 1:
            variants = tuple(dict.fromkeys(info.raw for info in group))
            duplicate_groups.append(
                DuplicateGroup(
                    normalized=normalized,
                    variants=variants,
                    count=len(group),
                    indices=tuple(info.index for info in group),
                )
            )
    duplicate_groups.sort(key=lambda group: group.indices[0])

    empty_entries = sum(1 for entry in entries if entry.is_empty)
    missing_entries = tuple(info.raw for info in entries if not info.is_empty and not info.exists)

    return PathAnalysis(
        entries=tuple(entries),
        duplicate_groups=tuple(duplicate_groups),
        empty_entries=empty_entries,
        missing_entries=missing_entries,
    )


def is_script_shim(path: str) -> bool:
    """Whether *path* is a script (batch/VBScript/JS) rather than a native binary."""
    extension = os.path.splitext(path)[1].lower()
    return extension in _SCRIPT_EXTENSIONS
