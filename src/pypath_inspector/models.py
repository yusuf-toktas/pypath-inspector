"""Shared data models for PyPath Inspector.

Every model is a plain dataclass so that the discovery, probing and analysis
layers can assemble results, the diagnostics layer can reason about them and
the reporting layer can serialise them without custom plumbing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    """Severity of a diagnostic finding."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True)
class Finding:
    """A single actionable diagnostic result.

    Attributes:
        code: Stable machine-readable identifier, e.g. ``PIP_INTERPRETER_MISMATCH``.
        severity: How urgently the user should act on the finding.
        title: Short human-readable summary of the problem.
        evidence: Factual observations the finding is based on.
        explanation: Why the finding matters.
        remediation: Suggested, non-destructive next steps.
    """

    code: str
    severity: Severity
    title: str
    evidence: tuple[str, ...] = ()
    explanation: str = ""
    remediation: tuple[str, ...] = ()


@dataclass(frozen=True)
class CommandMatch:
    """One executable that PATH resolution would consider for a command name.

    Attributes:
        path: Full path of the matching executable.
        directory: The PATH entry (verbatim) the executable was found in.
        path_index: Zero-based index of that PATH entry.
    """

    path: str
    directory: str
    path_index: int


@dataclass(frozen=True)
class CommandResolution:
    """Resolution result for a single command name such as ``python``.

    Attributes:
        name: The command name that was resolved.
        resolved: Full path of the first match on PATH, or ``None``.
        matches: All matches across all PATH entries, in PATH order.
    """

    name: str
    resolved: str | None
    matches: tuple[CommandMatch, ...] = ()


@dataclass(frozen=True)
class PathEntryInfo:
    """A single entry of the PATH variable.

    Attributes:
        index: Zero-based position of the entry within PATH.
        raw: The entry exactly as it appears in PATH.
        normalized: Case- and separator-normalised form used for comparisons.
        exists: Whether the entry points to an existing directory.
        is_empty: Whether the entry is empty (meaning "current directory").
    """

    index: int
    raw: str
    normalized: str
    exists: bool
    is_empty: bool


@dataclass(frozen=True)
class DuplicateGroup:
    """A set of PATH entries that normalise to the same directory.

    Attributes:
        normalized: The shared normalised directory.
        variants: Distinct raw spellings of the entry, in first-seen order.
        count: How many PATH entries belong to this group.
        indices: PATH entry indices belonging to this group.
    """

    normalized: str
    variants: tuple[str, ...]
    count: int
    indices: tuple[int, ...]


@dataclass(frozen=True)
class PathAnalysis:
    """Structured analysis of the PATH variable.

    Attributes:
        entries: Every PATH entry, in order.
        duplicate_groups: Groups of entries that normalise to the same directory.
        empty_entries: Number of empty entries (each means "current directory").
        missing_entries: Raw entries that do not point to an existing directory.
    """

    entries: tuple[PathEntryInfo, ...] = ()
    duplicate_groups: tuple[DuplicateGroup, ...] = ()
    empty_entries: int = 0
    missing_entries: tuple[str, ...] = ()


@dataclass(frozen=True)
class Interpreter:
    """A Python interpreter discovered on the machine.

    Attributes:
        path: Path as discovered (may be a symlink or alias).
        real_path: Path after resolving symlinks, used for deduplication.
        version: Version string when known, ``None`` otherwise.
        sources: Where it was discovered: ``PATH``, ``py-launcher`` or ``uv``.
        aliases: Command names on PATH that resolve to this interpreter.
    """

    path: str
    real_path: str
    version: str | None
    sources: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class InterpreterProbe:
    """Result of executing a Python interpreter to inspect its internals.

    Attributes:
        executable: The executable that was probed.
        ok: Whether the interpreter could be queried successfully.
        version: ``platform.python_version()`` of the probed interpreter.
        sys_executable: ``sys.executable`` as reported by the interpreter.
        base_executable: ``sys._base_executable`` when available (venv support).
        prefix: ``sys.prefix`` of the probed interpreter.
        base_prefix: ``sys.base_prefix`` of the probed interpreter.
        is_venv: Whether ``sys.prefix != sys.base_prefix``.
        error_kind: Machine-readable failure reason when ``ok`` is false.
        error_detail: Truncated command output captured while failing.
        store_stub: Whether the executable looks like the Microsoft Store
            "app execution alias" stub that opens the Store instead of Python.
    """

    executable: str
    ok: bool
    version: str | None = None
    sys_executable: str | None = None
    base_executable: str | None = None
    prefix: str | None = None
    base_prefix: str | None = None
    is_venv: bool | None = None
    error_kind: str | None = None
    error_detail: str | None = None
    store_stub: bool = False


@dataclass(frozen=True)
class PipVersionInfo:
    """Parsed output of a ``pip --version`` style invocation.

    Attributes:
        origin: Human-readable origin, e.g. ``pip command on PATH``.
        command: The command that was executed.
        ok: Whether the command ran and its output could be parsed.
        pip_version: Pip's own version, e.g. ``24.0``.
        python_version: Python version pip reports, e.g. ``3.12``.
        install_path: Path of the pip package that produced the output.
        resolved_path: Path of the executable that was run, when known.
        error_kind: Machine-readable failure reason when ``ok`` is false.
        error_detail: Truncated command output captured while failing.
    """

    origin: str
    command: str
    ok: bool
    pip_version: str | None = None
    python_version: str | None = None
    install_path: str | None = None
    resolved_path: str | None = None
    error_kind: str | None = None
    error_detail: str | None = None


@dataclass(frozen=True)
class PipAnalysis:
    """Comparison between pip commands and the active interpreter.

    Attributes:
        pip_on_path: Result of running the ``pip`` command found on PATH.
        pip3_on_path: Result of running the ``pip3`` command found on PATH.
        python_m_pip: Result of running ``python -m pip --version``.
        mismatch: Whether any inconsistency was detected at all.
        targets_other_python: Whether the pip command on PATH installs into
            a different interpreter than the ``python`` command runs.
        installations_differ: Whether the pip command and ``python -m pip``
            are different pip installations (different version or path)
            while targeting the same Python version.
        mismatch_reasons: Human-readable explanation of each inconsistency.
    """

    pip_on_path: PipVersionInfo | None = None
    pip3_on_path: PipVersionInfo | None = None
    python_m_pip: PipVersionInfo | None = None
    mismatch: bool = False
    targets_other_python: bool = False
    installations_differ: bool = False
    mismatch_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class VenvAnalysis:
    """Virtual environment state of the primary interpreter.

    Values of environment variables are never exposed; only booleans that
    describe whether they are present and consistent.

    Attributes:
        probed: Whether a Python interpreter was probed at all.
        probe_ok: Whether that probe succeeded.
        in_venv: Whether the interpreter runs inside a virtual environment.
        prefix: ``sys.prefix`` of the active interpreter.
        base_prefix: ``sys.base_prefix`` of the active interpreter.
        base_executable: The interpreter the virtual environment is based on.
        pyvenv_cfg_present: Whether ``pyvenv.cfg`` exists next to the prefix.
        virtual_env_set: Whether the ``VIRTUAL_ENV`` variable is set.
        virtual_env_consistent: Whether ``VIRTUAL_ENV`` matches the prefix.
        conda_prefix_set: Whether the ``CONDA_PREFIX`` variable is set.
    """

    probed: bool = False
    probe_ok: bool = False
    in_venv: bool | None = None
    prefix: str | None = None
    base_prefix: str | None = None
    base_executable: str | None = None
    pyvenv_cfg_present: bool | None = None
    virtual_env_set: bool = False
    virtual_env_consistent: bool | None = None
    conda_prefix_set: bool = False


@dataclass(frozen=True)
class PlatformInfo:
    """Information about the machine and the Python running PyPath Inspector.

    Attributes:
        system: Operating system name, e.g. ``Windows``.
        release: Operating system release, e.g. ``11``.
        version: Operating system version string.
        machine: Machine architecture, e.g. ``AMD64``.
        host_python: Version of the Python running PyPath Inspector itself.
        host_executable: Executable of the Python running PyPath Inspector.
    """

    system: str
    release: str
    version: str
    machine: str
    host_python: str
    host_executable: str


@dataclass(frozen=True)
class PythonCommandState:
    """Resolution and probe state for a primary Python command.

    Attributes:
        name: The command name, ``python`` or ``python3``.
        resolved: Full path of the first PATH match, or ``None``.
        probe: The probe result for the resolved executable, if probed.
    """

    name: str
    resolved: str | None
    probe: InterpreterProbe | None = None


@dataclass(frozen=True)
class DoctorReport:
    """Complete result of a ``pypath doctor`` run.

    Attributes:
        tool_name: Package name of the tool itself.
        tool_version: Version of the tool itself.
        generated_at: ISO-8601 UTC timestamp of the run.
        platform: Machine and host interpreter information.
        commands: Command resolution results, one per inspected command.
        path: Structured PATH analysis.
        interpreters: All discovered Python interpreters.
        discovery_notes: Caveats and non-fatal issues from discovery.
        python: State of the primary ``python`` command.
        python3: State of the ``python3`` command.
        pip: Pip and interpreter consistency analysis.
        venv: Virtual environment analysis.
        findings: All diagnostic findings, ordered by severity.
    """

    tool_name: str
    tool_version: str
    generated_at: str
    platform: PlatformInfo
    commands: tuple[CommandResolution, ...]
    path: PathAnalysis
    interpreters: tuple[Interpreter, ...]
    discovery_notes: tuple[str, ...]
    python: PythonCommandState
    python3: PythonCommandState
    pip: PipAnalysis
    venv: VenvAnalysis
    findings: tuple[Finding, ...] = field(default=())

    @property
    def worst_severity(self) -> Severity | None:
        """Highest severity among all findings, or ``None`` when empty."""
        if any(f.severity is Severity.ERROR for f in self.findings):
            return Severity.ERROR
        if any(f.severity is Severity.WARNING for f in self.findings):
            return Severity.WARNING
        if self.findings:
            return Severity.INFO
        return None

    @property
    def exit_code(self) -> int:
        """Automation-friendly exit code derived from the findings."""
        worst = self.worst_severity
        if worst is Severity.ERROR:
            return 2
        if worst is Severity.WARNING:
            return 1
        return 0

    @property
    def counts(self) -> dict[str, int]:
        """Number of findings per severity."""
        return {
            "info": sum(1 for f in self.findings if f.severity is Severity.INFO),
            "warning": sum(1 for f in self.findings if f.severity is Severity.WARNING),
            "error": sum(1 for f in self.findings if f.severity is Severity.ERROR),
        }
