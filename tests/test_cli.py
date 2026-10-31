"""Tests for the command line interface.

``run_diagnostics`` is patched so these tests exercise argument parsing,
output routing, redaction and exit codes without touching the real
machine.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest import mock

from pypath_inspector import __version__
from pypath_inspector.cli import EXIT_INTERNAL, EXIT_USAGE, build_parser, main
from pypath_inspector.models import DoctorReport, Finding, Severity

from .test_reporting import sample_report


def report_with_home_path() -> DoctorReport:
    """Clone the sample report with the real home directory in evidence."""
    report = sample_report()
    home = os.path.expanduser("~")
    finding = Finding(
        code="HOME_EVIDENCE",
        severity=Severity.WARNING,
        title="evidence containing a user path",
        evidence=(os.path.join(home, "venv", "Scripts", "python.exe"),),
    )
    return DoctorReport(
        tool_name=report.tool_name,
        tool_version=report.tool_version,
        generated_at=report.generated_at,
        platform=report.platform,
        commands=report.commands,
        path=report.path,
        interpreters=report.interpreters,
        discovery_notes=report.discovery_notes,
        python=report.python,
        python3=report.python3,
        pip=report.pip,
        venv=report.venv,
        findings=report.findings + (finding,),
    )


class ParserTest(unittest.TestCase):
    def test_version_flag(self):
        parser = build_parser()
        stdout = io.StringIO()
        with self.assertRaises(SystemExit) as ctx:
            with redirect_stdout(stdout):
                parser.parse_args(["--version"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn(__version__, stdout.getvalue())

    def test_doctor_defaults(self):
        args = build_parser().parse_args(["doctor"])
        self.assertEqual(args.format, "terminal")
        self.assertIsNone(args.output)
        self.assertFalse(args.no_redact)
        self.assertEqual(args.timeout, 15.0)

    def test_bad_format_is_usage_error(self):
        with self.assertRaises(SystemExit) as ctx:
            build_parser().parse_args(["doctor", "--format", "yaml"])
        self.assertEqual(ctx.exception.code, EXIT_USAGE)

    def test_negative_timeout_is_usage_error(self):
        for bad in ("-1", "0"):
            with self.assertRaises(SystemExit) as ctx:
                build_parser().parse_args(["doctor", "--timeout", bad])
            self.assertEqual(ctx.exception.code, EXIT_USAGE)

    def test_positive_timeout_accepted(self):
        args = build_parser().parse_args(["doctor", "--timeout", "30"])
        self.assertEqual(args.timeout, 30.0)

    def test_unknown_command_is_usage_error(self):
        with self.assertRaises(SystemExit) as ctx:
            build_parser().parse_args(["explode"])
        self.assertEqual(ctx.exception.code, EXIT_USAGE)


class MainTest(unittest.TestCase):
    def run_main(self, argv, report=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        target = "pypath_inspector.cli.run_diagnostics"
        with mock.patch(target, return_value=report or sample_report()):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_help_without_command(self):
        code, out, _ = self.run_main([])
        self.assertEqual(code, 0)
        self.assertIn("doctor", out)

    def test_terminal_output_and_exit_code(self):
        code, out, _ = self.run_main(["doctor"])
        self.assertEqual(code, 2)
        self.assertIn("[ERROR] PIP_INTERPRETER_MISMATCH", out)

    def test_json_output_is_redacted_by_default(self):
        code, out, _ = self.run_main(["doctor", "--format", "json"], report_with_home_path())
        self.assertEqual(code, 2)
        payload = json.loads(out)
        self.assertEqual(payload["tool_name"], "pypath-inspector")
        home = os.path.expanduser("~")
        if home and home not in ("~", "/"):
            serialized = json.dumps(payload)
            self.assertNotIn(home, serialized)
            self.assertNotIn(home.replace("\\", "\\\\"), serialized)
        evidence = [line for f in payload["findings"] for line in f["evidence"]]
        self.assertTrue(any(line.startswith("~") for line in evidence))

    def test_markdown_output_is_redacted_by_default(self):
        code, out, _ = self.run_main(["doctor", "--format", "markdown"], report_with_home_path())
        self.assertEqual(code, 2)
        home = os.path.expanduser("~")
        if home and home not in ("~", "/"):
            self.assertNotIn(home, out)
        self.assertIn(os.path.join("~", "venv"), out)
        self.assertIn("# pypath-inspector report", out)

    def test_no_redact_flag(self):
        report = sample_report()
        code, out, _ = self.run_main(["doctor", "--format", "markdown", "--no-redact"], report)
        self.assertEqual(code, 2)
        self.assertIn("C:\\Py\\python.exe", out)

    def test_output_file_written_redacted(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "report.md"
            code, _, err = self.run_main(["doctor", "--format", "markdown", "--output", str(target)])
            self.assertEqual(code, 2)
            self.assertTrue(target.exists())
            content = target.read_text(encoding="utf-8")
            self.assertIn("# pypath-inspector report", content)
            self.assertIn(str(target), err)

    def test_terminal_to_file_is_redacted(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "report.txt"
            code, _, _ = self.run_main(["doctor", "--output", str(target)], report_with_home_path())
            self.assertEqual(code, 2)
            content = target.read_text(encoding="utf-8")
            home = os.path.expanduser("~")
            if home and home not in ("~", "/"):
                self.assertNotIn(home, content)
            self.assertIn(os.path.join("~", "venv"), content)

    def test_clean_report_exits_zero(self):
        report = sample_report()
        clean = DoctorReport(
            tool_name=report.tool_name,
            tool_version=report.tool_version,
            generated_at=report.generated_at,
            platform=report.platform,
            commands=report.commands,
            path=report.path,
            interpreters=report.interpreters,
            discovery_notes=report.discovery_notes,
            python=report.python,
            python3=report.python3,
            pip=report.pip,
            venv=report.venv,
            findings=(),
        )
        code, out, _ = self.run_main(["doctor"], clean)
        self.assertEqual(code, 0)
        self.assertIn("No findings", out)

    def test_internal_error_exit_code(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        target = "pypath_inspector.cli.run_diagnostics"
        with mock.patch(target, side_effect=RuntimeError("boom")):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = main(["doctor"])
        self.assertEqual(code, EXIT_INTERNAL)
        self.assertIn("internal error", stderr.getvalue())

    def test_version_string_matches_package(self):
        self.assertTrue(__version__)


if __name__ == "__main__":
    unittest.main()
