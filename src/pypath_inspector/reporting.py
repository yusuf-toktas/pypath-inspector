"""Rendering of DoctorReport into terminal, JSON and Markdown output.

All renderers are pure functions from a :class:`DoctorReport` (plus an
optional redaction home) to text, which keeps them easy to test and makes
the CLI a thin adapter.
"""

from __future__ import annotations

import dataclasses
import json
from enum import Enum
from typing import Any

from .models import DoctorReport, Finding, Severity

_WIDTH = 78

_SEVERITY_LABEL = {
    Severity.INFO: "[INFO]",
    Severity.WARNING: "[WARNING]",
    Severity.ERROR: "[ERROR]",
}


def report_to_dict(report: DoctorReport) -> dict[str, Any]:
    """Convert a report into a JSON-serialisable dictionary."""
    data = dataclasses.asdict(report)
    data["exit_code"] = report.exit_code
    data["counts"] = report.counts
    data["worst_severity"] = report.worst_severity.value if report.worst_severity else None
    return _plain(data)


def _plain(value: Any) -> Any:
    """Convert enums and tuples into plain JSON types, recursively."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def render_json(report: DoctorReport) -> str:
    """Render the report as pretty-printed JSON."""
    return json.dumps(report_to_dict(report), indent=2, ensure_ascii=False)


def render_terminal(report: DoctorReport) -> str:
    """Render the report as a human-readable plain-text report."""
    lines: list[str] = []
    lines.append(f"{report.tool_name} {report.tool_version} - Python environment doctor")
    lines.append("=" * _WIDTH)
    lines.append(
        f"Generated: {report.generated_at} | "
        f"Platform: {report.platform.system} {report.platform.release} "
        f"({report.platform.machine})"
    )
    lines.append(
        f"Running under Python {report.platform.host_python} "
        f"(pypath itself: {report.platform.host_executable})"
    )
    lines.append("")

    lines.append(f"PYTHON INTERPRETERS ({len(report.interpreters)} discovered)")
    lines.append("-" * _WIDTH)
    if report.interpreters:
        for index, interpreter in enumerate(report.interpreters, start=1):
            sources = ", ".join(interpreter.sources)
            version = interpreter.version or "version unknown"
            aliases = f" | aliases: {', '.join(interpreter.aliases)}" if interpreter.aliases else ""
            lines.append(f"  {index}. {interpreter.path}")
            lines.append(f"      {version} [{sources}]{aliases}")
    else:
        lines.append("  none discovered")
    if report.discovery_notes:
        for note in report.discovery_notes:
            lines.append(f"  note: {note}")
    lines.append("")

    lines.append("COMMAND RESOLUTION")
    lines.append("-" * _WIDTH)
    for command in report.commands:
        if command.resolved:
            extra = f" ({len(command.matches)} matches)" if len(command.matches) > 1 else ""
            lines.append(f"  {command.name:<9} -> {command.resolved}{extra}")
        else:
            lines.append(f"  {command.name:<9} -> not found")
    lines.append("")

    lines.append("PATH ANALYSIS")
    lines.append("-" * _WIDTH)
    lines.append(f"  entries: {len(report.path.entries)}")
    lines.append(f"  duplicate groups: {len(report.path.duplicate_groups)}")
    lines.append(f"  empty entries: {report.path.empty_entries}")
    lines.append(f"  missing directories: {len(report.path.missing_entries)}")
    lines.append("")

    lines.append("VIRTUAL ENVIRONMENT")
    lines.append("-" * _WIDTH)
    venv = report.venv
    if venv is None:
        lines.append("  not analysed")
    elif not venv.probed:
        lines.append("  not inspected (no python command resolved)")
    elif not venv.probe_ok:
        lines.append("  unknown (the python command could not be probed)")
    elif venv.in_venv:
        lines.append(f"  active: yes (prefix {venv.prefix})")
        lines.append(f"  base prefix: {venv.base_prefix}")
        if venv.base_executable:
            lines.append(f"  base interpreter: {venv.base_executable}")
        lines.append(f"  pyvenv.cfg present: {venv.pyvenv_cfg_present}")
    else:
        lines.append("  active: no (system/base interpreter)")
    if venv is not None and venv.virtual_env_set:
        lines.append(
            "  VIRTUAL_ENV variable: set and "
            + ("consistent" if venv.virtual_env_consistent else "inconsistent")
        )
    lines.append("")

    lines.append("PIP ANALYSIS")
    lines.append("-" * _WIDTH)
    pip_infos = ()
    if report.pip is not None:
        pip_infos = (report.pip.pip_on_path, report.pip.pip3_on_path, report.pip.python_m_pip)
    if not any(info is not None for info in pip_infos):
        lines.append("  not analysed")
    for info in pip_infos:
        if info is None:
            continue
        if info.ok:
            lines.append(
                f"  {info.origin}: pip {info.pip_version} from {info.install_path} "
                f"(python {info.python_version})"
            )
        else:
            detail = f" ({info.error_detail})" if info.error_detail else ""
            lines.append(f"  {info.origin}: failed ({info.error_kind}){detail}")
    if report.pip is not None and report.pip.mismatch:
        for reason in report.pip.mismatch_reasons:
            lines.append(f"  mismatch: {reason}")
    lines.append("")

    counts = report.counts
    lines.append(
        f"FINDINGS ({len(report.findings)}: "
        f"{counts['error']} error, {counts['warning']} warning, {counts['info']} info)"
    )
    lines.append("=" * _WIDTH)
    if not report.findings:
        lines.append("  No findings. Nothing suspicious detected.")
    for finding in report.findings:
        lines.extend(_render_finding_terminal(finding))
    lines.append("")
    lines.append(f"Exit code: {report.exit_code}")
    return "\n".join(lines)


def _render_finding_terminal(finding: Finding) -> list[str]:
    lines = [f"  {_SEVERITY_LABEL[finding.severity]} {finding.code}: {finding.title}"]
    for item in finding.evidence:
        lines.append(f"      - {item}")
    if finding.explanation:
        lines.append(f"      why: {finding.explanation}")
    for item in finding.remediation:
        lines.append(f"      fix: {item}")
    lines.append("")
    return lines


def render_markdown(report: DoctorReport) -> str:
    """Render the report as a Markdown document."""
    counts = report.counts
    lines: list[str] = []
    lines.append(f"# {report.tool_name} report")
    lines.append("")
    lines.append(f"- **Generated:** {report.generated_at}")
    lines.append(
        f"- **Platform:** {report.platform.system} {report.platform.release} "
        f"({report.platform.machine})"
    )
    lines.append(f"- **Running under Python:** {report.platform.host_python}")
    lines.append(
        f"- **Findings:** {counts['error']} error, {counts['warning']} warning, "
        f"{counts['info']} info"
    )
    lines.append(f"- **Exit code:** {report.exit_code}")
    lines.append("")

    lines.append("## Python interpreters")
    lines.append("")
    if report.interpreters:
        lines.append("| # | Path | Version | Sources | Aliases |")
        lines.append("|---|------|---------|---------|---------|")
        for index, interpreter in enumerate(report.interpreters, start=1):
            path = _md_code(interpreter.path)
            version = interpreter.version or "unknown"
            sources = ", ".join(interpreter.sources)
            aliases = ", ".join(interpreter.aliases) if interpreter.aliases else "-"
            lines.append(f"| {index} | {path} | {version} | {sources} | {aliases} |")
    else:
        lines.append("None discovered.")
    if report.discovery_notes:
        lines.append("")
        lines.append("Notes:")
        for note in report.discovery_notes:
            lines.append(f"- {note}")
    lines.append("")

    lines.append("## Command resolution")
    lines.append("")
    lines.append("| Command | Resolved to | Matches |")
    lines.append("|---------|-------------|---------|")
    for command in report.commands:
        resolved = _md_code(command.resolved) if command.resolved else "not found"
        lines.append(f"| `{command.name}` | {resolved} | {len(command.matches)} |")
    lines.append("")

    lines.append("## PATH analysis")
    lines.append("")
    lines.append(f"- Entries: {len(report.path.entries)}")
    lines.append(f"- Duplicate groups: {len(report.path.duplicate_groups)}")
    lines.append(f"- Empty entries: {report.path.empty_entries}")
    lines.append(f"- Missing directories: {len(report.path.missing_entries)}")
    if report.path.duplicate_groups:
        lines.append("")
        lines.append("Duplicate groups:")
        for group in report.path.duplicate_groups:
            indices = ", ".join(str(i) for i in group.indices)
            lines.append(f"- {_md_code(group.normalized)} x{group.count} (entries {indices})")
    lines.append("")

    lines.append("## Virtual environment")
    lines.append("")
    venv = report.venv
    if venv is None:
        lines.append("Not analysed.")
    elif not venv.probed:
        lines.append("Not inspected (no python command resolved).")
    elif not venv.probe_ok:
        lines.append("Unknown (the python command could not be probed).")
    else:
        lines.append(f"- Inside virtual environment: {'yes' if venv.in_venv else 'no'}")
        lines.append(f"- Prefix: {_md_code(venv.prefix)}")
        lines.append(f"- Base prefix: {_md_code(venv.base_prefix)}")
        if venv.base_executable:
            lines.append(f"- Base interpreter: {_md_code(venv.base_executable)}")
        if venv.in_venv:
            lines.append(f"- pyvenv.cfg present: {venv.pyvenv_cfg_present}")
    if venv is not None and venv.virtual_env_set:
        state = "consistent" if venv.virtual_env_consistent else "inconsistent"
        lines.append(f"- VIRTUAL_ENV variable: set ({state})")
    lines.append("")

    lines.append("## Pip analysis")
    lines.append("")
    pip_infos = ()
    if report.pip is not None:
        pip_infos = (report.pip.pip_on_path, report.pip.pip3_on_path, report.pip.python_m_pip)
    if not any(info is not None for info in pip_infos):
        lines.append("Not analysed.")
    for info in pip_infos:
        if info is None:
            continue
        if info.ok:
            lines.append(
                f"- {info.origin}: pip {info.pip_version} from "
                f"{_md_code(info.install_path)} (python {info.python_version})"
            )
        else:
            lines.append(f"- {info.origin}: failed ({info.error_kind})")
    if report.pip is not None and report.pip.mismatch:
        lines.append("")
        lines.append("Mismatches:")
        for reason in report.pip.mismatch_reasons:
            lines.append(f"- {reason}")
    lines.append("")

    lines.append("## Findings")
    lines.append("")
    if not report.findings:
        lines.append("No findings. Nothing suspicious detected.")
    for finding in report.findings:
        lines.append(f"### {_SEVERITY_LABEL[finding.severity]} {finding.code}")
        lines.append("")
        lines.append(finding.title)
        lines.append("")
        if finding.evidence:
            lines.append("Evidence:")
            for item in finding.evidence:
                lines.append(f"- {item}")
            lines.append("")
        if finding.explanation:
            lines.append(f"**Why it matters:** {finding.explanation}")
            lines.append("")
        if finding.remediation:
            lines.append("**How to fix:**")
            for item in finding.remediation:
                lines.append(f"- {item}")
            lines.append("")
    return "\n".join(lines) + "\n"


def _md_code(text: str | None) -> str:
    """Wrap text in backticks, tolerating missing values."""
    if not text:
        return "-"
    return f"`{text}`"
