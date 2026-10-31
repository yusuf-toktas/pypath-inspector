"""Tests for subprocess probing, parsing and failure handling."""

from __future__ import annotations

import sys
import unittest

from pypath_inspector.probing import (
    CommandResult,
    is_within_path,
    looks_like_store_stub,
    major_minor,
    make_runner,
    parse_pip_version,
    probe_interpreter,
    probe_pip,
)

from .fakes import FakeRunner, fail, interpreter_json, ok


class MakeRunnerTest(unittest.TestCase):
    """The real runner must capture output and survive every failure mode."""

    def test_successful_command(self):
        runner = make_runner(timeout=10)
        result = runner([sys.executable, "-c", "print(42)"])
        self.assertTrue(result.ok)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "42")

    def test_nonzero_exit(self):
        runner = make_runner(timeout=10)
        result = runner([sys.executable, "-c", "raise SystemExit(3)"])
        self.assertFalse(result.ok)
        self.assertEqual(result.returncode, 3)

    def test_missing_executable(self):
        runner = make_runner(timeout=10)
        result = runner(["definitely-not-a-real-command-xyz"])
        self.assertEqual(result.error, "not-found")
        self.assertIsNone(result.returncode)

    def test_timeout(self):
        runner = make_runner(timeout=0.2)
        result = runner([sys.executable, "-c", "import time; time.sleep(5)"])
        self.assertTrue(result.timed_out)
        self.assertEqual(result.error, "timeout")

    def test_empty_command(self):
        runner = make_runner(timeout=10)
        result = runner([])
        self.assertEqual(result.error, "empty-command")


class ProbeInterpreterTest(unittest.TestCase):
    """Interpreter probing via the fake runner."""

    def test_json_probe_success(self):
        runner = FakeRunner()
        exe = r"C:\Py\python.exe"
        runner.add([exe, "-c"], ok(interpreter_json()))
        probe = probe_interpreter(exe, runner)
        self.assertTrue(probe.ok)
        self.assertEqual(probe.version, "3.12.1")
        self.assertEqual(probe.prefix, "C:\\Py")
        self.assertFalse(probe.is_venv)

    def test_json_probe_venv(self):
        runner = FakeRunner()
        exe = r"C:\venv\Scripts\python.exe"
        runner.add(
            [exe, "-c"],
            ok(
                interpreter_json(
                    version="3.12.1",
                    executable=exe,
                    prefix=r"C:\venv",
                    base_prefix=r"C:\Py",
                )
            ),
        )
        probe = probe_interpreter(exe, runner)
        self.assertTrue(probe.ok)
        self.assertTrue(probe.is_venv)

    def test_version_fallback(self):
        runner = FakeRunner()
        exe = "/usr/bin/python2"
        runner.add([exe, "-c"], fail())
        runner.add([exe, "--version"], ok("Python 2.7.18\n"))
        probe = probe_interpreter(exe, runner)
        self.assertTrue(probe.ok)
        self.assertEqual(probe.version, "2.7.18")
        self.assertIsNone(probe.is_venv)

    def test_version_fallback_on_stderr(self):
        runner = FakeRunner()
        exe = "/usr/bin/python2"
        runner.add([exe, "-c"], fail())
        runner.add([exe, "--version"], CommandResult((), 0, "", "Python 2.7.18\n", False, None))
        probe = probe_interpreter(exe, runner)
        self.assertTrue(probe.ok)
        self.assertEqual(probe.version, "2.7.18")

    def test_failure_records_error_kind(self):
        runner = FakeRunner()
        exe = r"C:\broken\python.exe"
        runner.add([exe, "-c"], fail("exit-9009", stderr="boom"))
        runner.add([exe, "--version"], fail("exit-9009", stderr="boom"))
        probe = probe_interpreter(exe, runner)
        self.assertFalse(probe.ok)
        self.assertIsNotNone(probe.error_kind)
        self.assertIn("boom", probe.error_detail)

    def test_store_stub_detected_by_message(self):
        runner = FakeRunner()
        exe = r"C:\Users\u\AppData\Local\Microsoft\WindowsApps\python3.exe"
        message = (
            "Python was not found; run without arguments to install from the "
            "Microsoft Store, or disable this shortcut from Settings > Apps > "
            "Advanced app settings > App execution aliases."
        )
        runner.add([exe, "-c"], fail("exit-9009", stderr=message, returncode=9009))
        runner.add([exe, "--version"], fail("exit-9009", stderr=message, returncode=9009))
        probe = probe_interpreter(exe, runner)
        self.assertFalse(probe.ok)
        self.assertTrue(probe.store_stub)

    def test_store_stub_detected_by_path(self):
        runner = FakeRunner()
        exe = r"C:\Users\u\AppData\Local\Microsoft\WindowsApps\python.exe"
        runner.add([exe, "-c"], fail("timeout"))
        runner.add([exe, "--version"], fail("timeout"))
        probe = probe_interpreter(exe, runner)
        self.assertFalse(probe.ok)
        self.assertTrue(probe.store_stub)

    def test_working_windows_store_python_is_not_a_stub(self):
        runner = FakeRunner()
        exe = r"C:\Users\u\AppData\Local\Microsoft\WindowsApps\python.exe"
        runner.add([exe, "-c"], ok(interpreter_json(version="3.13.0")))
        probe = probe_interpreter(exe, runner)
        self.assertTrue(probe.ok)
        self.assertFalse(probe.store_stub)


class ParsePipVersionTest(unittest.TestCase):
    """Parsing of ``pip --version`` output."""

    def test_parse_typical_output(self):
        parsed = parse_pip_version(
            "pip 24.0 from C:\\Program Files\\Python312\\Lib\\site-packages\\pip (python 3.12)\n"
        )
        self.assertEqual(parsed, ("24.0", "C:\\Program Files\\Python312\\Lib\\site-packages\\pip", "3.12"))

    def test_parse_garbage(self):
        self.assertIsNone(parse_pip_version("command not found"))
        self.assertIsNone(parse_pip_version(""))


class ProbePipTest(unittest.TestCase):
    """Pip probing via the fake runner."""

    def test_success(self):
        runner = FakeRunner()
        pip = r"C:\Py\Scripts\pip.exe"
        runner.add([pip, "--version"], ok("pip 24.0 from C:\\Py\\Lib\\site-packages\\pip (python 3.12)"))
        info = probe_pip([pip, "--version"], "pip command on PATH", runner, resolved_path=pip)
        self.assertTrue(info.ok)
        self.assertEqual(info.pip_version, "24.0")
        self.assertEqual(info.python_version, "3.12")
        self.assertEqual(info.resolved_path, pip)

    def test_failure(self):
        runner = FakeRunner()
        info = probe_pip(["pip", "--version"], "pip command on PATH", runner)
        self.assertFalse(info.ok)
        self.assertEqual(info.error_kind, "not-found")


class HelpersTest(unittest.TestCase):
    """Small helper functions."""

    def test_major_minor(self):
        self.assertEqual(major_minor("3.12.1"), "3.12")
        self.assertEqual(major_minor("3.15"), "3.15")
        self.assertIsNone(major_minor("abc"))
        self.assertIsNone(major_minor(None))

    def test_is_within_path(self):
        self.assertTrue(is_within_path(r"C:\Py\Lib\site-packages\pip", "C:\\Py"))
        self.assertTrue(is_within_path("C:\\Py", "C:\\Py"))
        self.assertFalse(is_within_path("C:\\Other", "C:\\Py"))

    def test_looks_like_store_stub(self):
        self.assertTrue(looks_like_store_stub("Python was not found; ..."))
        self.assertTrue(looks_like_store_stub("... install from the Microsoft Store ..."))
        self.assertFalse(looks_like_store_stub("Python 3.12.1"))


if __name__ == "__main__":
    unittest.main()
