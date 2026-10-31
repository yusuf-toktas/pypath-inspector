"""Command line interface for PyPath Inspector.

Exit codes (stable, automation-friendly):

* ``0`` - diagnostics completed, no findings above INFO
* ``1`` - diagnostics completed, WARNING findings present
* ``2`` - diagnostics completed, ERROR findings present
* ``3`` - usage error (unknown command or option)
* ``4`` - internal failure
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from . import __version__
from .diagnostics import run_diagnostics
from .models import DoctorReport
from .redaction import default_home, redact_text, redact_value
from .reporting import render_json, render_markdown, render_terminal, report_to_dict

EXIT_OK = 0
EXIT_WARNING = 1
EXIT_ERROR = 2
EXIT_USAGE = 3
EXIT_INTERNAL = 4

_FORMATS = ("terminal", "json", "markdown")


class _ArgumentParser(argparse.ArgumentParser):
    """Argument parser that exits with the documented usage exit code."""

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{self.prog}: error: {message}\n")


def _positive_float(value: str) -> float:
    """Parse a float that must be strictly positive.

    A non-positive timeout would silently disable the subprocess timeout
    guarantee (on Windows a negative timeout means "wait forever"), so it
    is rejected as a usage error instead.
    """
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid float value: {value!r}")
    if number <= 0:
        raise argparse.ArgumentTypeError("timeout must be greater than zero")
    return number


def build_parser() -> argparse.ArgumentParser:
    """Build the pypath argument parser."""
    parser = _ArgumentParser(
        prog="pypath",
        description=(
            "PyPath Inspector: a local-first, read-only diagnostic tool for "
            "Python installations, PATH configuration, command resolution, "
            "pip/interpreter mismatches and virtual environments."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="print the pypath version and exit",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    doctor = subparsers.add_parser(
        "doctor",
        help="diagnose the local Python environment",
        description=(
            "Run all diagnostics and print a report. Exit code reflects the "
            "worst finding: 0 clean, 1 warnings, 2 errors."
        ),
    )
    doctor.add_argument(
        "--format",
        choices=_FORMATS,
        default="terminal",
        help="report format (default: terminal)",
    )
    doctor.add_argument(
        "--output",
        metavar="FILE",
        help="write the report to FILE instead of the terminal",
    )
    doctor.add_argument(
        "--no-redact",
        action="store_true",
        help=(
            "disable home-directory redaction in JSON and Markdown reports "
            "(redaction is on by default)"
        ),
    )
    doctor.add_argument(
        "--timeout",
        type=_positive_float,
        default=15.0,
        metavar="SECONDS",
        help="timeout for every external command (default: 15)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the pypath CLI and return the process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return EXIT_OK

    try:
        report = run_diagnostics(timeout=args.timeout)
        text, confirm = _render(report, args)
        if args.output:
            with open(args.output, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
            if confirm:
                print(confirm, file=sys.stderr)
        else:
            print(text)
        return report.exit_code
    except Exception as exc:  # pragma: no cover - last-resort guard
        print(f"pypath: internal error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


def _render(report: DoctorReport, args: argparse.Namespace) -> tuple[str, str | None]:
    """Render the report honouring format, output and redaction rules.

    Redaction of the user's home directory applies to the JSON and
    Markdown formats and to anything written to a file; plain terminal
    output keeps full paths so remediation stays copy-pasteable.
    """
    confirm = f"Report written to {args.output}" if args.output else None
    redact = not args.no_redact and (args.format in ("json", "markdown") or args.output is not None)

    if not redact:
        return _render_format(report, args.format), confirm

    home = default_home()
    if args.format == "json":
        data = redact_value(report_to_dict(report), home)
        return json.dumps(data, indent=2, ensure_ascii=False), confirm
    text = _render_format(report, args.format)
    return redact_text(text, home), confirm


def _render_format(report: DoctorReport, fmt: str) -> str:
    if fmt == "json":
        return render_json(report)
    if fmt == "markdown":
        return render_markdown(report)
    return render_terminal(report)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
