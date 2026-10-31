"""Tests for virtual environment detection and consistency checks."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pypath_inspector.models import InterpreterProbe
from pypath_inspector.venvcheck import analyze_venv


def probe(
    ok: bool = True,
    prefix: str | None = r"C:\Py",
    base_prefix: str | None = r"C:\Py",
    base_executable: str | None = None,
) -> InterpreterProbe:
    is_venv = None
    if ok and prefix and base_prefix:
        is_venv = prefix != base_prefix
    return InterpreterProbe(
        executable=r"C:\Py\python.exe",
        ok=ok,
        version="3.12.1" if ok else None,
        prefix=prefix,
        base_prefix=base_prefix,
        base_executable=base_executable,
        is_venv=is_venv,
    )


class AnalyzeVenvTest(unittest.TestCase):
    """Venv state derived from probe results and environment presence."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_system_interpreter(self):
        analysis = analyze_venv(probe(), {})
        self.assertTrue(analysis.probed)
        self.assertTrue(analysis.probe_ok)
        self.assertFalse(analysis.in_venv)
        self.assertFalse(analysis.virtual_env_set)

    def test_venv_detected_with_config(self):
        venv_dir = self.root / "venv"
        venv_dir.mkdir()
        (venv_dir / "pyvenv.cfg").write_text("home = C:\\Py\n", encoding="ascii")
        analysis = analyze_venv(
            probe(prefix=str(venv_dir), base_prefix=r"C:\Py", base_executable=r"C:\Py\python.exe"),
            {},
        )
        self.assertTrue(analysis.in_venv)
        self.assertTrue(analysis.pyvenv_cfg_present)
        self.assertEqual(analysis.base_executable, r"C:\Py\python.exe")

    def test_venv_missing_config(self):
        venv_dir = self.root / "venv"
        venv_dir.mkdir()
        analysis = analyze_venv(probe(prefix=str(venv_dir), base_prefix=r"C:\Py"), {})
        self.assertTrue(analysis.in_venv)
        self.assertFalse(analysis.pyvenv_cfg_present)

    def test_virtual_env_consistent(self):
        venv_dir = self.root / "venv"
        venv_dir.mkdir()
        analysis = analyze_venv(
            probe(prefix=str(venv_dir), base_prefix=r"C:\Py"),
            {"VIRTUAL_ENV": str(venv_dir)},
        )
        self.assertTrue(analysis.virtual_env_set)
        self.assertTrue(analysis.virtual_env_consistent)

    def test_virtual_env_stale(self):
        analysis = analyze_venv(probe(), {"VIRTUAL_ENV": r"C:\gone\venv"})
        self.assertTrue(analysis.virtual_env_set)
        self.assertFalse(analysis.virtual_env_consistent)
        self.assertFalse(analysis.in_venv)

    def test_conda_prefix_presence(self):
        analysis = analyze_venv(probe(), {"CONDA_PREFIX": r"C:\conda\envs\x"})
        self.assertTrue(analysis.conda_prefix_set)

    def test_values_are_never_reported(self):
        secret = r"C:\Users\secret\venv"
        analysis = analyze_venv(probe(), {"VIRTUAL_ENV": secret, "CONDA_PREFIX": secret})
        data = repr(analysis)
        self.assertNotIn("secret", data)

    def test_no_probe(self):
        analysis = analyze_venv(None, {})
        self.assertFalse(analysis.probed)
        self.assertFalse(analysis.probe_ok)
        self.assertIsNone(analysis.in_venv)

    def test_failed_probe(self):
        analysis = analyze_venv(probe(ok=False), {"VIRTUAL_ENV": r"C:\venv"})
        self.assertTrue(analysis.probed)
        self.assertFalse(analysis.probe_ok)
        self.assertIsNone(analysis.in_venv)
        self.assertFalse(analysis.virtual_env_consistent)


if __name__ == "__main__":
    unittest.main()
