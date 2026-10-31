"""Tests for pip / interpreter mismatch detection."""

from __future__ import annotations

import unittest

from pypath_inspector.models import CommandMatch, CommandResolution
from pypath_inspector.pipcheck import analyze_pip
from pypath_inspector.probing import CommandResult, probe_pip, parse_pip_version

from .fakes import FakeRunner, fail, ok

PY = r"C:\Py\python.exe"
PY2 = r"C:\Py2\python.exe"


def resolution(name: str, resolved: str | None) -> CommandResolution:
    matches = (CommandMatch(path=resolved, directory=r"C:\dir", path_index=0),) if resolved else ()
    return CommandResolution(name=name, resolved=resolved, matches=matches)


class AnalyzePipTest(unittest.TestCase):
    """Pip analysis scenarios with mocked subprocess output."""

    def _probe(self, version: str, prefix: str = r"C:\Py"):
        from pypath_inspector.models import InterpreterProbe

        return InterpreterProbe(executable=PY, ok=True, version=version, prefix=prefix, base_prefix=prefix)

    def test_consistent_pip(self):
        runner = FakeRunner()
        runner.add(
            [r"C:\Py\Scripts\pip.exe", "--version"],
            ok(r"pip 24.0 from C:\Py\Lib\site-packages\pip (python 3.12)"),
        )
        runner.add(
            [PY, "-m", "pip", "--version"],
            ok(r"pip 24.0 from C:\Py\Lib\site-packages\pip (python 3.12)"),
        )
        analysis = analyze_pip(
            runner,
            resolution("pip", r"C:\Py\Scripts\pip.exe"),
            resolution("pip3", r"C:\Py\Scripts\pip3.exe"),
            PY,
            self._probe("3.12.1"),
        )
        self.assertFalse(analysis.mismatch)
        self.assertTrue(analysis.pip_on_path.ok)
        self.assertTrue(analysis.python_m_pip.ok)

    def test_version_mismatch_is_error_level(self):
        runner = FakeRunner()
        runner.add([r"C:\Py2\Scripts\pip.exe", "--version"], ok("pip 23.0 from C:\\Py2\\Lib\\site-packages\\pip (python 3.11)"))
        runner.add([PY, "-m", "pip", "--version"], ok("pip 24.0 from C:\\Py\\Lib\\site-packages\\pip (python 3.12)"))
        analysis = analyze_pip(
            runner,
            resolution("pip", r"C:\Py2\Scripts\pip.exe"),
            resolution("pip3", None),
            PY,
            self._probe("3.12.1"),
        )
        self.assertTrue(analysis.mismatch)
        self.assertTrue(analysis.targets_other_python)
        self.assertFalse(analysis.installations_differ)
        self.assertTrue(analysis.mismatch_reasons)

    def test_outside_prefix_is_mismatch(self):
        runner = FakeRunner()
        runner.add([r"C:\Py2\Scripts\pip.exe", "--version"], ok("pip 24.0 from C:\\Py2\\Lib\\site-packages\\pip (python 3.12)"))
        runner.add([PY, "-m", "pip", "--version"], ok("pip 24.0 from C:\\Py\\Lib\\site-packages\\pip (python 3.12)"))
        analysis = analyze_pip(
            runner,
            resolution("pip", r"C:\Py2\Scripts\pip.exe"),
            resolution("pip3", None),
            PY,
            self._probe("3.12.1"),
        )
        self.assertTrue(analysis.mismatch)
        self.assertTrue(analysis.targets_other_python)

    def test_different_pip_installations_same_python(self):
        runner = FakeRunner()
        runner.add([r"C:\Py\Scripts\pip.exe", "--version"], ok("pip 23.0 from C:\\Py\\Lib\\site-packages\\pip (python 3.12)"))
        runner.add([PY, "-m", "pip", "--version"], ok("pip 24.0 from C:\\Py\\Lib\\site-packages\\pip (python 3.12)"))
        analysis = analyze_pip(
            runner,
            resolution("pip", r"C:\Py\Scripts\pip.exe"),
            resolution("pip3", None),
            PY,
            self._probe("3.12.1"),
        )
        self.assertTrue(analysis.mismatch)
        self.assertTrue(analysis.installations_differ)
        self.assertFalse(analysis.targets_other_python)

    def test_pip_not_on_path(self):
        runner = FakeRunner()
        runner.add([PY, "-m", "pip", "--version"], ok("pip 24.0 from C:\\Py\\Lib\\site-packages\\pip (python 3.12)"))
        analysis = analyze_pip(runner, resolution("pip", None), resolution("pip3", None), PY, self._probe("3.12.1"))
        self.assertIsNone(analysis.pip_on_path)
        self.assertTrue(analysis.python_m_pip.ok)
        self.assertFalse(analysis.mismatch)

    def test_python_m_pip_fails(self):
        runner = FakeRunner()
        runner.add([PY, "-m", "pip", "--version"], fail("exit-1", stderr="No module named pip"))
        analysis = analyze_pip(runner, resolution("pip", None), resolution("pip3", None), PY, self._probe("3.12.1"))
        self.assertFalse(analysis.python_m_pip.ok)
        self.assertFalse(analysis.mismatch)

    def test_no_python_resolved(self):
        analysis = analyze_pip(FakeRunner(), resolution("pip", None), resolution("pip3", None), None, None)
        self.assertIsNone(analysis.python_m_pip)
        self.assertFalse(analysis.mismatch)

    def test_pip_command_exists_but_fails(self):
        runner = FakeRunner()
        runner.add([r"C:\Py\Scripts\pip.exe", "--version"], fail("exit-5", stderr="broken shim"))
        analysis = analyze_pip(
            runner,
            resolution("pip", r"C:\Py\Scripts\pip.exe"),
            resolution("pip3", None),
            PY,
            self._probe("3.12.1"),
        )
        self.assertFalse(analysis.pip_on_path.ok)
        self.assertFalse(analysis.mismatch)


class PosixPipAnalysisTest(unittest.TestCase):
    """Pip mismatch detection with POSIX-style paths.

    These scenarios must behave identically on every host: the install
    path and the interpreter prefix both use POSIX syntax, so the
    containment check must use posixpath semantics even when the tests
    run on Windows.
    """

    PY = "/home/u/venv/bin/python"

    def _probe(self, prefix: str):
        from pypath_inspector.models import InterpreterProbe

        return InterpreterProbe(
            executable=self.PY,
            ok=True,
            version="3.12.1",
            prefix=prefix,
            base_prefix=prefix,
        )

    def test_posix_consistent_pip(self):
        runner = FakeRunner()
        line = "pip 24.0 from /home/u/venv/lib/python3.12/site-packages/pip (python 3.12)"
        runner.add(["/home/u/venv/bin/pip", "--version"], ok(line))
        runner.add([self.PY, "-m", "pip", "--version"], ok(line))
        analysis = analyze_pip(
            runner,
            resolution("pip", "/home/u/venv/bin/pip"),
            resolution("pip3", None),
            self.PY,
            self._probe("/home/u/venv"),
        )
        self.assertFalse(analysis.mismatch)
        self.assertFalse(analysis.targets_other_python)

    def test_posix_pip_outside_prefix_is_mismatch(self):
        runner = FakeRunner()
        runner.add(
            ["/home/u/other/bin/pip", "--version"],
            ok("pip 24.0 from /home/u/other/lib/python3.12/site-packages/pip (python 3.12)"),
        )
        runner.add([self.PY, "-m", "pip", "--version"], ok(
            "pip 24.0 from /home/u/venv/lib/python3.12/site-packages/pip (python 3.12)"
        ))
        analysis = analyze_pip(
            runner,
            resolution("pip", "/home/u/other/bin/pip"),
            resolution("pip3", None),
            self.PY,
            self._probe("/home/u/venv"),
        )
        self.assertTrue(analysis.mismatch)
        self.assertTrue(analysis.targets_other_python)

    def test_posix_prefix_boundary_respected(self):
        runner = FakeRunner()
        runner.add(
            ["/home/u/venv2/bin/pip", "--version"],
            ok("pip 24.0 from /home/u/venv2/lib/python3.12/site-packages/pip (python 3.12)"),
        )
        runner.add([self.PY, "-m", "pip", "--version"], ok(
            "pip 24.0 from /home/u/venv/lib/python3.12/site-packages/pip (python 3.12)"
        ))
        analysis = analyze_pip(
            runner,
            resolution("pip", "/home/u/venv2/bin/pip"),
            resolution("pip3", None),
            self.PY,
            self._probe("/home/u/venv"),
        )
        self.assertTrue(analysis.mismatch)
        self.assertTrue(analysis.targets_other_python)

    def test_mixed_flavor_paths_report_mismatch(self):
        runner = FakeRunner()
        runner.add(
            ["/home/u/venv/bin/pip", "--version"],
            ok(r"pip 24.0 from C:\Py\Lib\site-packages\pip (python 3.12)"),
        )
        runner.add([self.PY, "-m", "pip", "--version"], ok(
            "pip 24.0 from /home/u/venv/lib/python3.12/site-packages/pip (python 3.12)"
        ))
        analysis = analyze_pip(
            runner,
            resolution("pip", "/home/u/venv/bin/pip"),
            resolution("pip3", None),
            self.PY,
            self._probe("/home/u/venv"),
        )
        self.assertTrue(analysis.mismatch)
        self.assertTrue(analysis.targets_other_python)


class ProbePipDetailsTest(unittest.TestCase):
    def test_command_string_and_origin(self):
        runner = FakeRunner()
        runner.add([PY, "-m", "pip", "--version"], ok("pip 24.0 from C:\\Py\\Lib\\site-packages\\pip (python 3.12)"))
        info = probe_pip([PY, "-m", "pip", "--version"], "python -m pip", runner)
        self.assertEqual(info.command, f"{PY} -m pip --version")
        self.assertEqual(info.origin, "python -m pip")

    def test_unparseable_output_is_failure(self):
        runner = FakeRunner()
        runner.add([PY, "-m", "pip", "--version"], CommandResult((PY,), 0, "weird output", "", False, None))
        info = probe_pip([PY, "-m", "pip", "--version"], "python -m pip", runner)
        self.assertFalse(info.ok)
        self.assertEqual(info.error_kind, "bad-output")

    def test_parse_pip_version_module(self):
        parsed = parse_pip_version("pip 25.1 from /usr/lib/python3/dist-packages/pip (python 3.13)")
        self.assertEqual(parsed, ("25.1", "/usr/lib/python3/dist-packages/pip", "3.13"))


if __name__ == "__main__":
    unittest.main()
