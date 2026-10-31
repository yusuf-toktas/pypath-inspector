"""Integration tests for the full diagnostic pipeline.

Every scenario runs against temporary directories and a fake subprocess
runner, so results never depend on the developer machine.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from pypath_inspector.diagnostics import run_diagnostics
from pypath_inspector.models import Severity
from pypath_inspector.reporting import report_to_dict

from .fakes import FakeRunner, fail, interpreter_json, make_exec, ok

PATH_EXT = [".exe", ".bat"]

STORE_MESSAGE = (
    "Python was not found; run without arguments to install from the "
    "Microsoft Store, or disable this shortcut from Settings > Apps > "
    "Advanced app settings > App execution aliases."
)


class DiagnosticsScenario(unittest.TestCase):
    """Base class providing a fake machine built from temp directories."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.runner = FakeRunner()
        self.env = {"PATH": ""}

    def dir(self, name: str) -> Path:
        path = self.root / name
        path.mkdir(exist_ok=True)
        return path

    def add_python(self, directory: Path, version: str = "3.12.1", prefix: Path | None = None,
                   base_prefix: Path | None = None):
        """Create a python.exe and register successful probe responses."""
        exe = make_exec(directory, "python.exe")
        self.runner.add([str(exe), "-c"], ok(interpreter_json(
            version=version,
            executable=str(exe),
            prefix=str(prefix or directory),
            base_prefix=str(base_prefix if base_prefix is not None else (prefix or directory)),
        )))
        return exe

    def add_pip(self, exe: Path, line: str):
        self.runner.add([str(exe), "-m", "pip", "--version"], ok(line))

    def site_packages(self, base) -> str:
        """Host-flavoured site-packages path for fake pip output.

        Built with ``os.path.join`` so the pip install path matches the
        flavour of the temporary directories the scenario runs on; a
        hardcoded Windows separator would break containment checks on
        POSIX hosts.
        """
        return os.path.join(str(base), "Lib", "site-packages", "pip")

    def set_path(self, *directories):
        self.env["PATH"] = os.pathsep.join(str(item) for item in directories)

    def codes(self, report):
        return {finding.code for finding in report.findings}

    def finding(self, report, code):
        for finding in report.findings:
            if finding.code == code:
                return finding
        return None


class CleanEnvironmentTest(DiagnosticsScenario):
    """A single healthy installation produces no findings above INFO."""

    def test_clean_single_install(self):
        install = self.dir("install")
        python = self.add_python(install)
        scripts = self.dir("install")  # reuse: pip lives next to python here
        pip = make_exec(scripts, "pip.exe")
        self.runner.add([str(pip), "--version"], ok(
            f"pip 24.0 from {self.site_packages(install)} (python 3.12)"
        ))
        self.add_pip(python, f"pip 24.0 from {self.site_packages(install)} (python 3.12)")
        self.set_path(install)

        report = run_diagnostics(env=self.env, runner=self.runner, pathext=PATH_EXT)

        self.assertEqual(report.exit_code, 0)
        self.assertNotIn("PIP_INTERPRETER_MISMATCH", self.codes(report))
        self.assertNotIn("PATH_DUPLICATE_ENTRIES", self.codes(report))
        by_name = {command.name: command for command in report.commands}
        self.assertEqual(Path(by_name["python"].resolved), python)
        self.assertEqual(report.python.probe.version, "3.12.1")


class PathProblemTest(DiagnosticsScenario):
    """PATH configuration problems."""

    def test_duplicate_path_entries(self):
        install = self.dir("install")
        self.add_python(install)
        self.set_path(install, self.dir("other"), install)
        report = run_diagnostics(env=self.env, runner=self.runner, pathext=PATH_EXT)
        self.assertIn("PATH_DUPLICATE_ENTRIES", self.codes(report))
        self.assertEqual(report.exit_code, 1)
        finding = self.finding(report, "PATH_DUPLICATE_ENTRIES")
        self.assertEqual(finding.severity, Severity.WARNING)

    def test_empty_path_entry(self):
        install = self.dir("install")
        self.add_python(install)
        self.set_path(install, "")
        report = run_diagnostics(env=self.env, runner=self.runner, pathext=PATH_EXT)
        self.assertIn("PATH_EMPTY_ENTRY", self.codes(report))

    def test_missing_python_entirely(self):
        empty = self.dir("empty")
        self.set_path(empty)
        report = run_diagnostics(env=self.env, runner=self.runner, pathext=PATH_EXT)
        self.assertIn("PYTHON_NOT_FOUND", self.codes(report))
        self.assertEqual(report.exit_code, 2)
        self.assertEqual(report.interpreters, ())

    def test_empty_path_variable(self):
        report = run_diagnostics(env={"PATH": ""}, runner=self.runner, pathext=PATH_EXT)
        self.assertIn("PATH_MISSING", self.codes(report))


class StoreStubTest(DiagnosticsScenario):
    """The Windows Store alias stub scenario."""

    def test_python3_stub_detected(self):
        install = self.dir("install")
        python = self.add_python(install)
        apps = self.dir("Microsoft") / "WindowsApps"
        apps.mkdir(parents=True)
        stub = make_exec(apps, "python3.exe")
        self.runner.add([str(stub), "-c"], fail("exit-9009", stderr=STORE_MESSAGE, returncode=9009))
        self.runner.add([str(stub), "--version"], fail("exit-9009", stderr=STORE_MESSAGE, returncode=9009))
        self.set_path(install, apps)

        report = run_diagnostics(env=self.env, runner=self.runner, pathext=PATH_EXT)

        self.assertIn("WINDOWS_STORE_ALIAS_STUB", self.codes(report))
        self.assertEqual(report.exit_code, 2)
        self.assertEqual(report.python3.resolved, str(stub))
        self.assertEqual(report.python.resolved, str(python))
        finding = self.finding(report, "WINDOWS_STORE_ALIAS_STUB")
        self.assertEqual(finding.severity, Severity.ERROR)
        self.assertTrue(any(stub.name in line for line in finding.evidence))


class PipMismatchTest(DiagnosticsScenario):
    """Pip targeting another interpreter."""

    def test_pip_version_mismatch(self):
        install = self.dir("install")
        python = self.add_python(install, version="3.12.1")
        other = self.dir("other")
        pip = make_exec(other, "pip.exe")
        self.runner.add([str(pip), "--version"], ok(
            f"pip 23.0 from {self.site_packages(other)} (python 3.11)"
        ))
        self.add_pip(python, f"pip 24.0 from {self.site_packages(install)} (python 3.12)")
        self.set_path(install, other)

        report = run_diagnostics(env=self.env, runner=self.runner, pathext=PATH_EXT)

        self.assertIn("PIP_INTERPRETER_MISMATCH", self.codes(report))
        self.assertEqual(report.exit_code, 2)
        finding = self.finding(report, "PIP_INTERPRETER_MISMATCH")
        self.assertTrue(any("python -m pip" in line for line in finding.remediation))

    def test_pip_module_missing(self):
        install = self.dir("install")
        python = self.add_python(install)
        self.runner.add([str(python), "-m", "pip", "--version"], fail("exit-1", stderr="No module named pip"))
        self.set_path(install)
        report = run_diagnostics(env=self.env, runner=self.runner, pathext=PATH_EXT)
        self.assertIn("PIP_MODULE_MISSING", self.codes(report))

    def test_pip_not_on_path(self):
        install = self.dir("install")
        python = self.add_python(install)
        self.add_pip(python, f"pip 24.0 from {self.site_packages(install)} (python 3.12)")
        self.set_path(install)
        report = run_diagnostics(env=self.env, runner=self.runner, pathext=PATH_EXT)
        self.assertIn("PIP_NOT_ON_PATH", self.codes(report))


class VenvScenarioTest(DiagnosticsScenario):
    """Virtual environment reporting."""

    def test_venv_active(self):
        base = self.dir("base")
        self.add_python(base)
        venv = self.dir("venv")
        scripts = venv / "Scripts"
        venv_python = make_exec(scripts, "python.exe")
        self.runner.add([str(venv_python), "-c"], ok(interpreter_json(
            version="3.12.1",
            executable=str(venv_python),
            prefix=str(venv),
            base_prefix=str(base),
        )))
        pip = make_exec(scripts, "pip.exe")
        pip_line = f"pip 24.0 from {self.site_packages(venv)} (python 3.12)"
        self.runner.add([str(pip), "--version"], ok(pip_line))
        self.add_pip(venv_python, pip_line)
        (venv / "pyvenv.cfg").write_text(f"home = {base}\n", encoding="ascii")
        self.set_path(scripts, base)

        report = run_diagnostics(env=self.env, runner=self.runner, pathext=PATH_EXT)

        self.assertIn("VENV_ACTIVE", self.codes(report))
        self.assertTrue(report.venv.in_venv)
        self.assertEqual(Path(report.python.resolved), venv_python)
        self.assertTrue(report.venv.pyvenv_cfg_present)
        self.assertEqual(report.exit_code, 0)

    def test_stale_virtual_env_variable(self):
        base = self.dir("base")
        python = self.add_python(base)
        pip = make_exec(base, "pip.exe")
        pip_line = f"pip 24.0 from {self.site_packages(base)} (python 3.12)"
        self.runner.add([str(pip), "--version"], ok(pip_line))
        self.add_pip(python, pip_line)
        self.set_path(base)
        self.env["VIRTUAL_ENV"] = str(self.dir("gone"))
        report = run_diagnostics(env=self.env, runner=self.runner, pathext=PATH_EXT)
        self.assertIn("VENV_STALE_ENV_VAR", self.codes(report))
        self.assertEqual(report.exit_code, 1)

    def test_conda_prefix_is_info(self):
        base = self.dir("base")
        python = self.add_python(base)
        pip = make_exec(base, "pip.exe")
        pip_line = f"pip 24.0 from {self.site_packages(base)} (python 3.12)"
        self.runner.add([str(pip), "--version"], ok(pip_line))
        self.add_pip(python, pip_line)
        self.set_path(base)
        self.env["CONDA_PREFIX"] = str(self.dir("conda"))
        report = run_diagnostics(env=self.env, runner=self.runner, pathext=PATH_EXT)
        self.assertIn("CONDA_ENV_ACTIVE", self.codes(report))
        self.assertEqual(report.exit_code, 0)


class BrokenInterpreterTest(DiagnosticsScenario):
    """A python command that cannot be probed."""

    def test_probe_failure_reported(self):
        install = self.dir("install")
        python = make_exec(install, "python.exe")
        self.runner.add([str(python), "-c"], fail("exit-1", stderr="broken"))
        self.runner.add([str(python), "--version"], fail("exit-1", stderr="broken"))
        self.set_path(install)
        report = run_diagnostics(env=self.env, runner=self.runner, pathext=PATH_EXT)
        self.assertIn("PYTHON_PROBE_FAILED", self.codes(report))
        self.assertEqual(report.python.probe.ok, False)

    def test_probe_timeout_reported(self):
        install = self.dir("install")
        python = make_exec(install, "python.exe")
        self.runner.add([str(python), "-c"], fail("timeout"))
        self.runner.add([str(python), "--version"], fail("timeout"))
        self.set_path(install)
        report = run_diagnostics(env=self.env, runner=self.runner, pathext=PATH_EXT)
        self.assertIn("PROBE_TIMEOUT", self.codes(report))


class MultiInstallTest(DiagnosticsScenario):
    """Multiple installations and shadowing."""

    def test_shadowed_and_multiple(self):
        first = self.dir("first")
        second = self.dir("second")
        self.add_python(first)
        self.add_python(second, version="3.11.9")
        self.set_path(first, second)

        report = run_diagnostics(env=self.env, runner=self.runner, pathext=PATH_EXT)

        self.assertIn("COMMAND_SHADOWED", self.codes(report))
        self.assertIn("MULTIPLE_PYTHON_INSTALLATIONS", self.codes(report))
        by_name = {command.name: command for command in report.commands}
        self.assertEqual(len(by_name["python"].matches), 2)
        self.assertEqual(Path(report.python.resolved).parent, first)

    def test_script_shim_resolution(self):
        install = self.dir("install")
        shim = make_exec(install, "python.bat")
        self.set_path(install)
        report = run_diagnostics(env=self.env, runner=self.runner, pathext=PATH_EXT)
        self.assertIn("SCRIPT_SHIM_RESOLUTION", self.codes(report))
        self.assertEqual(report.python.resolved, str(shim))


class ReportShapeTest(DiagnosticsScenario):
    """Structural guarantees of the assembled report."""

    def test_report_shape(self):
        install = self.dir("install")
        python = self.add_python(install)
        self.set_path(install)
        report = run_diagnostics(env=self.env, runner=self.runner, pathext=PATH_EXT)

        self.assertEqual(report.tool_name, "pypath-inspector")
        self.assertEqual(report.tool_version, "0.1.0")
        self.assertEqual(len(report.commands), 7)
        names = [command.name for command in report.commands]
        self.assertEqual(names, ["python", "python3", "pythonw", "pip", "pip3", "py", "uv"])
        self.assertEqual(Path(report.python.resolved), python)
        self.assertEqual(report.counts["error"] + report.counts["warning"] + report.counts["info"],
                         len(report.findings))

    def test_json_export_round_trip(self):
        install = self.dir("install")
        self.add_python(install)
        self.set_path(install)
        report = run_diagnostics(env=self.env, runner=self.runner, pathext=PATH_EXT)
        payload = json.loads(json.dumps(report_to_dict(report)))
        self.assertEqual(payload["tool_name"], "pypath-inspector")
        self.assertEqual(payload["exit_code"], report.exit_code)
        self.assertIn("findings", payload)
        self.assertIn("counts", payload)


if __name__ == "__main__":
    unittest.main()
