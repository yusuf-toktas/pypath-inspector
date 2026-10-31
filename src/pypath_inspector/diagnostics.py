"""Orchestrates every analysis and turns the results into findings.

``run_diagnostics`` is the single entry point used by the CLI. It wires
together PATH analysis, command resolution, interpreter discovery, pip
analysis and virtual environment analysis, then converts the collected
evidence into ordered, actionable :class:`~pypath_inspector.models.Finding`
objects.
"""

from __future__ import annotations

import datetime
import os
import platform
import sys
from typing import Mapping

from . import __version__
from .discovery import discover_interpreters
from .models import (
    CommandResolution,
    DoctorReport,
    Finding,
    Interpreter,
    PathAnalysis,
    PlatformInfo,
    PythonCommandState,
    Severity,
)
from .pipcheck import analyze_pip
from .probing import DEFAULT_TIMEOUT, Runner, probe_interpreter
from .resolution import COMMAND_NAMES, analyze_path, default_pathext, is_script_shim, resolve_commands
from .venvcheck import analyze_venv

TOOL_NAME = "pypath-inspector"

_SEVERITY_ORDER = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}

_WINDOWS_SETTINGS_ALIAS = (
    "Settings > Apps > Advanced app settings > App execution aliases"
)


def run_diagnostics(
    *,
    timeout: float = DEFAULT_TIMEOUT,
    env: Mapping[str, str] | None = None,
    runner: Runner | None = None,
    pathext: list[str] | None = None,
) -> DoctorReport:
    """Run the full diagnostic pipeline.

    Args:
        timeout: Subprocess timeout in seconds for every external command.
        env: Environment mapping to inspect; defaults to ``os.environ``.
        runner: Subprocess runner; defaults to a real runner with *timeout*.
        pathext: PATHEXT extension list, ``None`` for the platform default.
            Tests pass an explicit list for deterministic cross-platform
            behaviour.

    Returns:
        A complete :class:`DoctorReport`; never raises.
    """
    if env is None:
        env = os.environ
    if runner is None:
        from .probing import make_runner

        runner = make_runner(timeout)

    path_var = env.get("PATH", "") or ""
    if pathext is None:
        pathext = default_pathext()

    path_analysis = analyze_path(path_var)
    commands = resolve_commands(COMMAND_NAMES, path_var, pathext)
    by_name = {command.name: command for command in commands}

    discovery = discover_interpreters(
        runner,
        path_var,
        pathext,
        py_path=by_name["py"].resolved,
        uv_path=by_name["uv"].resolved,
    )

    python_state = _python_state("python", by_name["python"], discovery.probes, runner)
    python3_state = _python_state("python3", by_name["python3"], discovery.probes, runner)
    primary = python_state if python_state.resolved else python3_state

    pip_analysis = analyze_pip(
        runner,
        by_name["pip"],
        by_name["pip3"],
        primary.resolved,
        primary.probe,
    )
    venv_analysis = analyze_venv(primary.probe, env)

    findings: list[Finding] = []
    findings.extend(_path_findings(path_analysis))
    findings.extend(_resolution_findings(commands))
    findings.extend(_discovery_findings(discovery.interpreters, discovery.notes))
    findings.extend(
        _python_findings(
            python_state, python3_state, primary, discovery.interpreters, discovery.probes
        )
    )
    findings.extend(_pip_findings(pip_analysis, primary))
    findings.extend(_venv_findings(venv_analysis))
    findings.extend(_timeout_findings(discovery.probes, pip_analysis))
    findings.sort(key=lambda finding: (_SEVERITY_ORDER[finding.severity], finding.code))

    return DoctorReport(
        tool_name=TOOL_NAME,
        tool_version=__version__,
        generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        platform=_platform_info(),
        commands=commands,
        path=path_analysis,
        interpreters=discovery.interpreters,
        discovery_notes=discovery.notes,
        python=python_state,
        python3=python3_state,
        pip=pip_analysis,
        venv=venv_analysis,
        findings=tuple(findings),
    )


def _platform_info() -> PlatformInfo:
    return PlatformInfo(
        system=platform.system(),
        release=platform.release(),
        version=platform.version(),
        machine=platform.machine(),
        host_python=platform.python_version(),
        host_executable=sys.executable,
    )


def _python_state(
    name: str,
    resolution: CommandResolution,
    probes: Mapping[str, object],
    runner: Runner,
) -> PythonCommandState:
    """Build the probe state for a python-family command.

    Probe results discovered during interpreter discovery are reused so no
    interpreter is executed twice.
    """
    if not resolution.resolved:
        return PythonCommandState(name=name, resolved=None, probe=None)
    key = os.path.normcase(os.path.realpath(resolution.resolved))
    probe = probes.get(key)
    if probe is None:
        probe = probe_interpreter(resolution.resolved, runner)
    return PythonCommandState(name=name, resolved=resolution.resolved, probe=probe)


def _path_findings(path: PathAnalysis) -> list[Finding]:
    findings: list[Finding] = []
    if not path.entries or all(entry.is_empty for entry in path.entries):
        findings.append(
            Finding(
                code="PATH_MISSING",
                severity=Severity.ERROR,
                title="The PATH environment variable is empty or unset",
                evidence=["PATH is empty or not set; command resolution cannot work."],
                explanation=(
                    "Without PATH the shell cannot locate python, pip or any other "
                    "command. Every diagnostic in this report is unreliable until "
                    "PATH is restored."
                ),
                remediation=(
                    "Restore PATH through System Properties > Environment Variables "
                    "(Windows) or your shell profile (POSIX).",
                ),
            )
        )
        return findings

    if path.duplicate_groups:
        evidence = [
            f"'{group.normalized}' appears {group.count} times "
            f"(PATH entries {', '.join(str(i) for i in group.indices)})"
            for group in path.duplicate_groups
        ]
        findings.append(
            Finding(
                code="PATH_DUPLICATE_ENTRIES",
                severity=Severity.WARNING,
                title=f"PATH contains {len(path.duplicate_groups)} duplicate entr"
                f"{'y' if len(path.duplicate_groups) == 1 else 'ies'}",
                evidence=tuple(evidence),
                explanation=(
                    "Duplicate PATH entries make resolution order harder to reason "
                    "about, slow down command lookup, and are usually leftovers from "
                    "repeated installer or profile edits. The first occurrence always "
                    "wins."
                ),
                remediation=(
                    "Review PATH and remove the duplicate entries by hand (System "
                    "Properties > Environment Variables on Windows, or your shell "
                    "profile on POSIX). pypath never modifies PATH for you.",
                ),
            )
        )

    if path.empty_entries:
        findings.append(
            Finding(
                code="PATH_EMPTY_ENTRY",
                severity=Severity.WARNING,
                title=f"PATH contains {path.empty_entries} empty entr"
                f"{'y' if path.empty_entries == 1 else 'ies'}",
                evidence=[
                    f"Empty PATH entries search the current working directory for "
                    f"executables ({path.empty_entries} found)."
                ],
                explanation=(
                    "An empty entry (a stray ';' or ':') means the current directory "
                    "is searched for commands. This is a security risk: a malicious "
                    "executable named python.exe in any folder you work in would be "
                    "executed."
                ),
                remediation=(
                    "Locate the empty entry (between two consecutive separators) and "
                    "remove the stray separator from PATH.",
                ),
            )
        )

    if path.missing_entries:
        evidence = [f"'{entry}' does not exist" for entry in path.missing_entries[:10]]
        hidden = len(path.missing_entries) - len(evidence)
        if hidden > 0:
            evidence.append(f"... and {hidden} more")
        findings.append(
            Finding(
                code="PATH_NONEXISTENT_ENTRIES",
                severity=Severity.INFO,
                title=f"PATH references {len(path.missing_entries)} director"
                f"{'y' if len(path.missing_entries) == 1 else 'ies'} that do not exist",
                evidence=tuple(evidence),
                explanation=(
                    "Non-existent PATH entries are harmless but usually point to "
                    "uninstalled software. They add noise when reasoning about "
                    "resolution order."
                ),
                remediation=(
                    "Remove the stale entries manually if you know which program "
                    "they belonged to.",
                ),
            )
        )
    return findings


def _resolution_findings(commands: tuple[CommandResolution, ...]) -> list[Finding]:
    findings: list[Finding] = []

    shadowed = [command for command in commands if len(command.matches) > 1]
    if shadowed:
        evidence = [
            f"{command.name}: {len(command.matches)} matches; first wins -> "
            f"{command.resolved}"
            for command in shadowed
        ]
        findings.append(
            Finding(
                code="COMMAND_SHADOWED",
                severity=Severity.INFO,
                title=f"{len(shadowed)} command name"
                f"{'s are' if len(shadowed) != 1 else ' is'} resolved by multiple PATH entries",
                evidence=tuple(evidence),
                explanation=(
                    "When a command name matches several PATH entries, only the "
                    "first match is executed. The other installations are shadowed: "
                    "they still exist, but running the command name never reaches "
                    "them."
                ),
                remediation=(
                    "Call shadowed executables by their full path when you need "
                    "them, or adjust PATH order so the intended installation comes "
                    "first.",
                ),
            )
        )

    script_shims = [
        command
        for command in commands
        if command.resolved and is_script_shim(command.resolved)
    ]
    if script_shims:
        evidence = [
            f"{command.name} resolves to script shim {command.resolved}"
            for command in script_shims
        ]
        findings.append(
            Finding(
                code="SCRIPT_SHIM_RESOLUTION",
                severity=Severity.WARNING,
                title="A core command resolves to a script instead of a native executable",
                evidence=tuple(evidence),
                explanation=(
                    "Batch/VBScript/JavaScript shims can mangle arguments, break "
                    "virtual environment activation and behave differently from the "
                    "real executable when invoked from other programs."
                ),
                remediation=(
                    "Prefer invoking the real executable directly, or replace the "
                    "shim with a proper installation whose directory is on PATH.",
                ),
            )
        )
    return findings


def _discovery_findings(
    interpreters: tuple[Interpreter, ...], notes: tuple[str, ...]
) -> list[Finding]:
    findings: list[Finding] = []

    uv_managed = [item for item in interpreters if "uv" in item.sources]
    if uv_managed:
        findings.append(
            Finding(
                code="UV_MANAGED_PYTHONS",
                severity=Severity.INFO,
                title=f"uv manages {len(uv_managed)} Python installation"
                f"{'' if len(uv_managed) == 1 else 's'}",
                evidence=tuple(f"{item.path} ({item.version or 'version unknown'})" for item in uv_managed),
                explanation=(
                    "These interpreters are managed by uv. They are only used when "
                    "uv selects them, when their directory is on PATH, or when a "
                    "project's virtual environment points at them."
                ),
                remediation=("Use 'uv python list' to review them.",),
            )
        )

    missing = [note for note in notes if "does not exist" in note]
    if missing:
        findings.append(
            Finding(
                code="MANAGER_LISTS_MISSING_INTERPRETER",
                severity=Severity.INFO,
                title="A Python manager lists an interpreter that is no longer installed",
                evidence=tuple(missing[:10]),
                explanation=(
                    "The launcher or manager still reports an interpreter whose "
                    "files are gone, typically after a manual uninstall. Selecting "
                    "that version will fail."
                ),
                remediation=(
                    "Reinstall or cleanly uninstall that version with the matching "
                    "manager to refresh its registry.",
                ),
            )
        )

    failed = [note for note in notes if "query failed" in note]
    if failed:
        findings.append(
            Finding(
                code="MANAGER_QUERY_FAILED",
                severity=Severity.WARNING,
                title="A Python manager could not be queried",
                evidence=tuple(failed),
                explanation=(
                    "The manager executable exists but did not answer successfully, "
                    "so interpreters known only to it may be missing from this "
                    "report."
                ),
                remediation=(
                    "Run the manager manually (for example 'py -0p') to see its "
                    "error message.",
                ),
            )
        )
    return findings


def _python_findings(
    python_state: PythonCommandState,
    python3_state: PythonCommandState,
    primary: PythonCommandState,
    interpreters: tuple[Interpreter, ...],
    probes: Mapping[str, object],
) -> list[Finding]:
    findings: list[Finding] = []

    stub_keys = {
        os.path.normcase(os.path.realpath(state.resolved))
        for state in (python_state, python3_state)
        if state.resolved and state.probe and state.probe.store_stub
    }
    for interpreter in interpreters:
        key = os.path.normcase(os.path.realpath(interpreter.path))
        probe = probes.get(key)
        if probe is not None and getattr(probe, "store_stub", False):
            stub_keys.add(key)

    if stub_keys:
        evidence: list[str] = []
        for state in (python_state, python3_state):
            if state.resolved and os.path.normcase(os.path.realpath(state.resolved)) in stub_keys:
                evidence.append(f"the {state.name} command resolves to {state.resolved}")
                if state.probe and state.probe.error_detail:
                    evidence.append(f"  output: {state.probe.error_detail}")
        for interpreter in interpreters:
            key = os.path.normcase(os.path.realpath(interpreter.path))
            resolved_keys = {
                os.path.normcase(os.path.realpath(state.resolved))
                for state in (python_state, python3_state)
                if state.resolved
            }
            if key in stub_keys and key not in resolved_keys:
                evidence.append(
                    f"{interpreter.path} (discovered on PATH) is a Store alias stub"
                )
        real = [
            item for item in interpreters if os.path.normcase(os.path.realpath(item.path)) not in stub_keys
        ]
        if real:
            evidence.append(
                "working interpreters discovered elsewhere: "
                + "; ".join(f"{item.path} ({item.version})" for item in real[:5])
            )
        findings.append(
            Finding(
                code="WINDOWS_STORE_ALIAS_STUB",
                severity=Severity.ERROR,
                title="Microsoft Store alias stubs are intercepting python commands",
                evidence=tuple(evidence),
                explanation=(
                    "Windows ships zero-byte 'app execution aliases' for python and "
                    "python3. When no Store Python is installed, running them prints "
                    "a hint and exits with a failure code, so scripts and tools that "
                    "call python break."
                ),
                remediation=(
                    f"Turn the aliases off in {_WINDOWS_SETTINGS_ALIAS}, or install "
                    "Python from python.org / the Microsoft Store, and make sure the "
                    "real installation's directory comes before WindowsApps in PATH.",
                ),
            )
        )

    if not python_state.resolved and not python3_state.resolved and not interpreters:
        findings.append(
            Finding(
                code="PYTHON_NOT_FOUND",
                severity=Severity.ERROR,
                title="No Python interpreter could be discovered",
                evidence=[
                    "python and python3 are not resolvable on PATH",
                    "the py launcher and uv reported no installations either",
                ],
                explanation=(
                    "Without a resolvable python command, pip, virtual environments "
                    "and every Python-based tool will fail."
                ),
                remediation=(
                    "Install Python from python.org, the Microsoft Store, or with a "
                    "manager such as uv or the py launcher, then ensure its "
                    "directory is on PATH.",
                ),
            )
        )

    if (
        primary.resolved
        and primary.probe
        and not primary.probe.ok
        and not primary.probe.store_stub
    ):
        detail = primary.probe.error_detail or "no output captured"
        findings.append(
            Finding(
                code="PYTHON_PROBE_FAILED",
                severity=Severity.WARNING,
                title=f"the {primary.name} command could not be inspected",
                evidence=[
                    f"{primary.name} resolves to {primary.resolved}",
                    f"failure: {primary.probe.error_kind} ({detail})",
                ],
                explanation=(
                    "The resolved executable exists on PATH but failed to behave "
                    "like a working Python interpreter. It may be a broken shim, an "
                    "incomplete uninstall, or a launcher that requires arguments."
                ),
                remediation=(
                    "Run the executable manually to see its error, and consider "
                    "removing or repairing the installation it belongs to.",
                ),
            )
        )

    installations = [
        item for item in interpreters if os.path.normcase(os.path.realpath(item.path)) not in stub_keys
    ]
    directories = {os.path.dirname(item.real_path) for item in installations}
    if len(directories) >= 2:
        evidence = [
            f"{item.path} ({item.version or 'version unknown'}) "
            f"[{', '.join(item.sources)}]"
            for item in installations
        ]
        findings.append(
            Finding(
                code="MULTIPLE_PYTHON_INSTALLATIONS",
                severity=Severity.INFO,
                title=(
                    f"{len(directories)} Python installations discovered "
                    f"({len(installations)} executables)"
                ),
                evidence=tuple(evidence),
                explanation=(
                    "Multiple installations are not a problem by themselves, but "
                    "only the first PATH match answers the python command. Package "
                    "installs can silently land in a different interpreter than the "
                    "one you run."
                ),
                remediation=(
                    "Prefer explicit interpreter paths or a manager (py, uv) when "
                    "precision matters, and always install packages with "
                    "'python -m pip' rather than a bare 'pip'.",
                ),
            )
        )
    return findings


def _pip_findings(analysis, primary: PythonCommandState) -> list[Finding]:
    findings: list[Finding] = []

    if analysis.mismatch and analysis.targets_other_python:
        findings.append(
            Finding(
                code="PIP_INTERPRETER_MISMATCH",
                severity=Severity.ERROR,
                title="the pip command installs into a different Python than python runs",
                evidence=tuple(analysis.mismatch_reasons),
                explanation=(
                    "Running 'pip install ...' will place packages into an "
                    "interpreter other than the one the 'python' command executes. "
                    "The package then imports fine in one interpreter and is "
                    "missing in the other - the most common 'module not found' "
                    "surprise on multi-installation machines."
                ),
                remediation=(
                    "Always install through the interpreter you run: "
                    f"'{primary.name} -m pip install <package>'.",
                    "Compare 'pip --version' with 'python -m pip --version' after "
                    "any installation change to confirm they agree.",
                ),
            )
        )
    elif analysis.mismatch and analysis.installations_differ:
        findings.append(
            Finding(
                code="PIP_VERSION_DISAGREEMENT",
                severity=Severity.WARNING,
                title="the pip command and python -m pip are different pip installations",
                evidence=tuple(analysis.mismatch_reasons),
                explanation=(
                    "The pip command on PATH and the pip module inside the active "
                    "interpreter are separate installations. They may have different "
                    "versions and behaviours even though they target the same Python."
                ),
                remediation=(
                    f"Prefer '{primary.name} -m pip ...' for predictable behaviour.",
                ),
            )
        )

    pip_missing_on_path = not analysis.pip_on_path or not analysis.pip_on_path.ok
    if pip_missing_on_path and analysis.python_m_pip and analysis.python_m_pip.ok:
        evidence = ["no usable pip command was found on PATH"]
        if analysis.pip_on_path and not analysis.pip_on_path.ok:
            evidence.append(
                f"pip resolved to {analysis.pip_on_path.resolved} but failed: "
                f"{analysis.pip_on_path.error_kind}"
            )
        findings.append(
            Finding(
                code="PIP_NOT_ON_PATH",
                severity=Severity.WARNING,
                title="no working pip command on PATH",
                evidence=tuple(evidence),
                explanation=(
                    "The Scripts directory of the active interpreter is probably "
                    "not on PATH. Bare 'pip' commands will fail or run a foreign "
                    "pip."
                ),
                remediation=(
                    f"Use '{primary.name} -m pip ...' which always targets the "
                    "running interpreter.",
                    "Add the interpreter's Scripts directory to PATH if you want a "
                    "bare pip command.",
                ),
            )
        )

    if (
        primary.probe
        and primary.probe.ok
        and (not analysis.python_m_pip or not analysis.python_m_pip.ok)
    ):
        detail = None
        if analysis.python_m_pip and not analysis.python_m_pip.ok:
            detail = f"{analysis.python_m_pip.error_kind}: {analysis.python_m_pip.error_detail}"
        findings.append(
            Finding(
                code="PIP_MODULE_MISSING",
                severity=Severity.WARNING,
                title="pip is not available inside the active interpreter",
                evidence=(
                    (detail,) if detail else (f"'{primary.name} -m pip --version' did not succeed",)
                ),
                explanation=(
                    "The interpreter works, but the pip module could not be run for "
                    "it, so packages cannot be installed into it with pip."
                ),
                remediation=(
                    f"Bootstrap pip with '{primary.name} -m ensurepip --default-pip' "
                    "(run it yourself; pypath never installs anything).",
                ),
            )
        )
    return findings


def _venv_findings(venv) -> list[Finding]:
    findings: list[Finding] = []

    if venv.in_venv:
        evidence = [
            f"active prefix: {venv.prefix}",
            f"base prefix: {venv.base_prefix}",
        ]
        if venv.base_executable:
            evidence.append(f"based on interpreter: {venv.base_executable}")
        findings.append(
            Finding(
                code="VENV_ACTIVE",
                severity=Severity.INFO,
                title="the python command runs inside a virtual environment",
                evidence=tuple(evidence),
                explanation=(
                    "Inside a virtual environment, 'python' and 'python -m pip' "
                    "act on the environment, not the base installation. This is "
                    "the recommended state for project work."
                ),
                remediation=(
                    "No action needed. 'deactivate' (or a new shell) returns to the "
                    "base interpreter.",
                ),
            )
        )

    if venv.in_venv and venv.pyvenv_cfg_present is False:
        findings.append(
            Finding(
                code="VENV_MISSING_CONFIG",
                severity=Severity.WARNING,
                title="virtual environment detected but pyvenv.cfg is missing",
                evidence=[f"prefix {venv.prefix} reports a venv but has no pyvenv.cfg"],
                explanation=(
                    "A venv without pyvenv.cfg was likely copied, moved or partially "
                    "deleted. Activation scripts and sys.prefix detection may "
                    "misbehave."
                ),
                remediation=(
                    "Recreate the environment ('python -m venv <dir>') and reinstall "
                    "its requirements if behaviour seems broken.",
                ),
            )
        )

    if venv.virtual_env_set and venv.virtual_env_consistent is False:
        if venv.in_venv:
            evidence = [
                "VIRTUAL_ENV is set but does not match the active interpreter's prefix",
                f"active prefix: {venv.prefix}",
            ]
            title = "VIRTUAL_ENV points at a different environment than the active one"
        else:
            evidence = [
                "VIRTUAL_ENV is set but the active interpreter is not in a virtual environment",
            ]
            title = "VIRTUAL_ENV is set while python runs outside any virtual environment"
        findings.append(
            Finding(
                code="VENV_STALE_ENV_VAR",
                severity=Severity.WARNING,
                title=title,
                evidence=tuple(evidence),
                explanation=(
                    "A stale VIRTUAL_ENV misleads tools (editors, pip wrappers, "
                    "prompt integrations) into using a deactivated environment. The "
                    "variable's value is intentionally not shown here."
                ),
                remediation=(
                    "Deactivate the old environment, start a fresh shell, or "
                    "re-activate the intended environment so the variable matches "
                    "reality again.",
                ),
            )
        )

    if venv.conda_prefix_set:
        findings.append(
            Finding(
                code="CONDA_ENV_ACTIVE",
                severity=Severity.INFO,
                title="a conda environment appears to be active",
                evidence=["CONDA_PREFIX is set"],
                explanation=(
                    "Conda environments are not venvs: sys.prefix equals "
                    "sys.base_prefix inside them, so venv-based detection does not "
                    "apply. Conda manages its own PATH entries."
                ),
                remediation=("Use 'conda activate/deactivate' to switch environments.",),
            )
        )
    return findings


def _timeout_findings(probes: Mapping[str, object], pip_analysis) -> list[Finding]:
    timed_out: list[str] = []
    for executable, probe in probes.items():
        if getattr(probe, "error_kind", None) == "timeout":
            timed_out.append(str(executable))
    for info in (pip_analysis.pip_on_path, pip_analysis.pip3_on_path, pip_analysis.python_m_pip):
        if info and not info.ok and info.error_kind == "timeout":
            timed_out.append(info.command)
    if not timed_out:
        return []
    return [
        Finding(
            code="PROBE_TIMEOUT",
            severity=Severity.WARNING,
            title="one or more probes timed out",
            evidence=tuple(f"{item} did not answer within the timeout" for item in timed_out),
            explanation=(
                "An executable that hangs instead of answering is itself a "
                "diagnostic signal: it may wait for input, be blocked by security "
                "software, or be a broken shim."
            ),
            remediation=(
                "Run the listed commands manually to see where they hang. Use "
                "'pypath doctor --timeout N' to allow more time.",
            ),
        )
    ]
