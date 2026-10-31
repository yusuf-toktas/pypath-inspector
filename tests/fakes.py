"""Shared test doubles and helpers.

The fakes keep every test independent of the developer machine: PATH
scanning happens inside temporary directories and subprocess execution is
replaced by a configurable :class:`FakeRunner`.
"""

from __future__ import annotations

import os
from pathlib import Path

from pypath_inspector.probing import CommandResult

DEFAULT_RESULT = CommandResult((), None, "", "", False, "not-found")


def ok(stdout: str = "", stderr: str = "", returncode: int = 0) -> CommandResult:
    """Build a successful command result."""
    return CommandResult((), returncode, stdout, stderr, False, None)


def fail(
    error: str = "exit-1",
    stdout: str = "",
    stderr: str = "",
    returncode: int | None = 1,
) -> CommandResult:
    """Build a failed command result."""
    return CommandResult((), returncode, stdout, stderr, False, error)


def timeout(argv: tuple[str, ...] = ()) -> CommandResult:
    """Build a timed-out command result."""
    return CommandResult(argv, None, "", "", True, "timeout")


class FakeRunner:
    """Configurable stand-in for the subprocess runner.

    Responses are matched by argv prefix: the first response whose prefix
    equals the beginning of the incoming argv wins. Unmatched commands
    return a ``not-found`` result. Every call is recorded in ``calls``.
    """

    def __init__(self, responses=None):
        self.responses: list[tuple[tuple[str, ...], CommandResult]] = [
            (tuple(prefix), result) for prefix, result in (responses or [])
        ]
        self.calls: list[tuple[str, ...]] = []

    def add(self, prefix, result: CommandResult) -> None:
        """Register a response for commands starting with *prefix*."""
        self.responses.append((tuple(prefix), result))

    def __call__(self, argv) -> CommandResult:
        argv = tuple(str(part) for part in argv)
        self.calls.append(argv)
        for prefix, result in self.responses:
            if argv[: len(prefix)] == prefix:
                return result
        return DEFAULT_RESULT


def make_exec(directory: Path, name: str) -> Path:
    """Create a fake executable file inside *directory*."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text("", encoding="ascii")
    if os.name != "nt":
        path.chmod(0o755)
    return path


def interpreter_json(
    version: str = "3.12.1",
    executable: str = "C:\\Py\\python.exe",
    prefix: str = "C:\\Py",
    base_prefix: str | None = None,
) -> str:
    """Build the JSON payload produced by the interpreter probe snippet."""
    import json

    return json.dumps(
        {
            "version": version,
            "executable": executable,
            "base_executable": None,
            "prefix": prefix,
            "base_prefix": base_prefix if base_prefix is not None else prefix,
        }
    )
