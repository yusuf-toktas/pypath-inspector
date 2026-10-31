"""Tests for terminal, JSON and Markdown report generation."""

from __future__ import annotations

import json
import unittest

from pypath_inspector.models import (
    CommandMatch,
    CommandResolution,
    DoctorReport,
    Finding,
    PathAnalysis,
    PlatformInfo,
    PythonCommandState,
    Severity,
)
from pypath_inspector.reporting import (
    render_json,
    render_markdown,
    render_terminal,
    report_to_dict,
)


def sample_report() -> DoctorReport:
    """Build a small deterministic report for renderer tests."""
    python_match = CommandMatch(path=r"C:\Py\python.exe", directory=r"C:\Py", path_index=0)
    commands = (
        CommandResolution("python", r"C:\Py\python.exe", (python_match,)),
        CommandResolution("pip", None, ()),
    )
    findings = (
        Finding(
            code="PIP_INTERPRETER_MISMATCH",
            severity=Severity.ERROR,
            title="pip installs into a different Python",
            evidence=("pip reports Python 3.11", "python runs Python 3.12"),
            explanation="Packages land in the wrong interpreter.",
            remediation=("Use python -m pip install.",),
        ),
        Finding(
            code="PATH_DUPLICATE_ENTRIES",
            severity=Severity.WARNING,
            title="PATH contains 1 duplicate entry",
            evidence=("'C:\\Py' appears 2 times",),
        ),
        Finding(
            code="VENV_ACTIVE",
            severity=Severity.INFO,
            title="inside a virtual environment",
        ),
    )
    return DoctorReport(
        tool_name="pypath-inspector",
        tool_version="0.1.0",
        generated_at="2026-01-01T00:00:00+00:00",
        platform=PlatformInfo(
            system="Windows",
            release="11",
            version="10.0",
            machine="AMD64",
            host_python="3.12.1",
            host_executable=r"C:\Py\python.exe",
        ),
        commands=commands,
        path=PathAnalysis(entries=(), duplicate_groups=(), empty_entries=0, missing_entries=()),
        interpreters=(),
        discovery_notes=(),
        python=PythonCommandState(name="python", resolved=r"C:\Py\python.exe"),
        python3=PythonCommandState(name="python3", resolved=None),
        pip=None,
        venv=None,
        findings=findings,
    )


class TerminalReportTest(unittest.TestCase):
    def test_contains_sections_and_findings(self):
        text = render_terminal(sample_report())
        for expected in (
            "PYTHON INTERPRETERS",
            "COMMAND RESOLUTION",
            "PATH ANALYSIS",
            "PIP ANALYSIS",
            "FINDINGS",
            "[ERROR] PIP_INTERPRETER_MISMATCH",
            "[WARNING] PATH_DUPLICATE_ENTRIES",
            "[INFO] VENV_ACTIVE",
            "Exit code: 2",
            "C:\\Py\\python.exe",
            "not found",
        ):
            self.assertIn(expected, text)

    def test_empty_findings_message(self):
        report = sample_report()
        report = DoctorReport(
            **{**report.__dict__, "findings": ()}
        )
        text = render_terminal(report)
        self.assertIn("No findings", text)
        self.assertIn("Exit code: 0", text)


class JsonReportTest(unittest.TestCase):
    def test_valid_json_with_enums_as_strings(self):
        text = render_json(sample_report())
        payload = json.loads(text)
        self.assertEqual(payload["tool_name"], "pypath-inspector")
        self.assertEqual(payload["findings"][0]["severity"], "ERROR")
        self.assertEqual(payload["exit_code"], 2)
        self.assertEqual(payload["counts"]["info"], 1)
        self.assertEqual(payload["worst_severity"], "ERROR")

    def test_report_to_dict_has_no_enum_objects(self):
        data = report_to_dict(sample_report())
        self.assertEqual(data["findings"][0]["severity"], "ERROR")


class MarkdownReportTest(unittest.TestCase):
    def test_structure(self):
        text = render_markdown(sample_report())
        for expected in (
            "# pypath-inspector report",
            "## Python interpreters",
            "## Command resolution",
            "## PATH analysis",
            "## Virtual environment",
            "## Pip analysis",
            "## Findings",
            "### [ERROR] PIP_INTERPRETER_MISMATCH",
            "**Why it matters:**",
            "**How to fix:**",
            "| `python` | `C:\\Py\\python.exe` | 1 |",
        ):
            self.assertIn(expected, text)

    def test_missing_values_render_placeholder(self):
        text = render_markdown(sample_report())
        self.assertIn("not found", text)


class ExitCodeTest(unittest.TestCase):
    def test_severity_to_exit_code(self):
        report = sample_report()
        self.assertEqual(report.exit_code, 2)
        self.assertEqual(report.worst_severity, Severity.ERROR)

        warning_only = DoctorReport(**{**report.__dict__, "findings": report.findings[1:2]})
        self.assertEqual(warning_only.exit_code, 1)

        info_only = DoctorReport(**{**report.__dict__, "findings": report.findings[2:3]})
        self.assertEqual(info_only.exit_code, 0)

        clean = DoctorReport(**{**report.__dict__, "findings": ()})
        self.assertEqual(clean.exit_code, 0)
        self.assertIsNone(clean.worst_severity)


if __name__ == "__main__":
    unittest.main()
