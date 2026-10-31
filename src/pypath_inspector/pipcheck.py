"""Pip and interpreter consistency analysis.

Runs ``pip --version``, ``pip3 --version`` and ``python -m pip --version``
and compares them with the interpreter that the ``python`` command actually
resolves to, to detect the classic "pip installs into a different Python"
foot-gun.
"""

from __future__ import annotations

from .models import CommandResolution, InterpreterProbe, PipAnalysis, PipVersionInfo
from .probing import Runner, is_within_path, major_minor, probe_pip


def analyze_pip(
    runner: Runner,
    pip_resolution: CommandResolution,
    pip3_resolution: CommandResolution,
    python_resolved: str | None,
    python_probe: InterpreterProbe | None,
) -> PipAnalysis:
    """Compare the pip commands on PATH with the active interpreter.

    Args:
        runner: Subprocess runner used for every pip invocation.
        pip_resolution: Resolution result for the ``pip`` command.
        pip3_resolution: Resolution result for the ``pip3`` command.
        python_resolved: Executable the primary ``python`` command resolves to.
        python_probe: Probe result for that executable, when available.

    Returns:
        A :class:`PipAnalysis`; never raises.
    """
    pip_on_path: PipVersionInfo | None = None
    if pip_resolution.resolved:
        pip_on_path = probe_pip(
            [pip_resolution.resolved, "--version"],
            origin="pip command on PATH",
            runner=runner,
            resolved_path=pip_resolution.resolved,
        )

    pip3_on_path: PipVersionInfo | None = None
    if pip3_resolution.resolved:
        pip3_on_path = probe_pip(
            [pip3_resolution.resolved, "--version"],
            origin="pip3 command on PATH",
            runner=runner,
            resolved_path=pip3_resolution.resolved,
        )

    python_m_pip: PipVersionInfo | None = None
    if python_resolved:
        python_m_pip = probe_pip(
            [python_resolved, "-m", "pip", "--version"],
            origin="python -m pip",
            runner=runner,
            resolved_path=python_resolved,
        )

    reasons, targets_other_python, installations_differ = _mismatch_reasons(
        pip_on_path, python_m_pip, python_probe
    )
    return PipAnalysis(
        pip_on_path=pip_on_path,
        pip3_on_path=pip3_on_path,
        python_m_pip=python_m_pip,
        mismatch=bool(reasons),
        targets_other_python=targets_other_python,
        installations_differ=installations_differ,
        mismatch_reasons=tuple(reasons),
    )


def _mismatch_reasons(
    pip_on_path: PipVersionInfo | None,
    python_m_pip: PipVersionInfo | None,
    python_probe: InterpreterProbe | None,
) -> tuple[list[str], bool, bool]:
    """Collect mismatch reasons plus structured outcome flags.

    Returns:
        ``(reasons, targets_other_python, installations_differ)``
    """
    reasons: list[str] = []
    targets_other_python = False
    installations_differ = False
    if not pip_on_path or not pip_on_path.ok:
        return reasons, targets_other_python, installations_differ

    if python_m_pip and python_m_pip.ok:
        pip_python = major_minor(pip_on_path.python_version)
        module_python = major_minor(python_m_pip.python_version)
        if pip_python and module_python and pip_python != module_python:
            targets_other_python = True
            reasons.append(
                f"the pip command on PATH reports Python {pip_python}, while "
                f"python -m pip reports Python {module_python}"
            )
        elif pip_on_path.pip_version != python_m_pip.pip_version or (
            pip_on_path.install_path != python_m_pip.install_path
        ):
            installations_differ = True
            reasons.append(
                f"the pip command on PATH is pip {pip_on_path.pip_version} from "
                f"{pip_on_path.install_path}, while python -m pip is pip "
                f"{python_m_pip.pip_version} from {python_m_pip.install_path}"
            )

    if python_probe and python_probe.ok:
        pip_python = major_minor(pip_on_path.python_version)
        probe_python = major_minor(python_probe.version)
        if pip_python and probe_python and pip_python != probe_python:
            targets_other_python = True
            reasons.append(
                f"the pip command on PATH belongs to Python {pip_python}, but the "
                f"python command runs Python {probe_python}"
            )
        if python_probe.prefix and pip_on_path.install_path:
            if not is_within_path(pip_on_path.install_path, python_probe.prefix):
                targets_other_python = True
                reasons.append(
                    f"the pip command on PATH is installed outside the active "
                    f"interpreter's prefix ({python_probe.prefix})"
                )

    return reasons, targets_other_python, installations_differ
