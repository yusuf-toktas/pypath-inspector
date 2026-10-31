"""Tests for interpreter discovery via PATH, py launcher and uv."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from pypath_inspector.discovery import discover_interpreters

from .fakes import FakeRunner, fail, interpreter_json, make_exec, ok


class DiscoveryTest(unittest.TestCase):
    """Discovery scenarios built from temporary directories and fake output."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.dir_a = self.root / "a"
        self.dir_a.mkdir()

    def test_path_scan_discovers_python_family(self):
        python = make_exec(self.dir_a, "python.exe")
        python3 = make_exec(self.dir_a, "python3.exe")
        pythonw = make_exec(self.dir_a, "pythonw.exe")
        runner = FakeRunner()
        runner.add([str(python), "-c"], ok(interpreter_json(version="3.12.1")))
        runner.add([str(python3), "-c"], ok(interpreter_json(version="3.12.1")))
        result = discover_interpreters(runner, str(self.dir_a), [".exe"])
        paths = {Path(item.path).name for item in result.interpreters}
        self.assertEqual(paths, {"python.exe", "python3.exe", "pythonw.exe"})
        by_name = {Path(item.path).name: item for item in result.interpreters}
        self.assertEqual(by_name["python.exe"].version, "3.12.1")
        self.assertIn("python", by_name["python.exe"].aliases)
        self.assertIn("pythonw", by_name["pythonw.exe"].aliases)

    def test_pythonw_is_not_executed_but_gets_sibling_version(self):
        python = make_exec(self.dir_a, "python.exe")
        pythonw = make_exec(self.dir_a, "pythonw.exe")
        runner = FakeRunner()
        runner.add([str(python), "-c"], ok(interpreter_json(version="3.13.2")))
        result = discover_interpreters(runner, str(self.dir_a), [".exe"])
        executed = [call[0] for call in runner.calls]
        self.assertNotIn(str(pythonw), executed)
        by_name = {Path(item.path).name: item for item in result.interpreters}
        self.assertEqual(by_name["pythonw.exe"].version, "3.13.2")

    def test_probe_failure_leaves_version_unknown(self):
        python = make_exec(self.dir_a, "python.exe")
        runner = FakeRunner()
        runner.add([str(python), "-c"], fail("exit-9009"))
        runner.add([str(python), "--version"], fail("exit-9009"))
        result = discover_interpreters(runner, str(self.dir_a), [".exe"])
        self.assertEqual(len(result.interpreters), 1)
        self.assertIsNone(result.interpreters[0].version)

    def test_py_launcher_output_parsed(self):
        python = make_exec(self.dir_a, "python.exe")
        py_exe = make_exec(self.root / "bin", "py.exe")
        output = f" -V:3.12 *        {python}\n -V:3.11          {self.root}\\missing\\python.exe\n"
        runner = FakeRunner()
        runner.add([str(python), "-c"], ok(interpreter_json(version="3.12.1")))
        runner.add([str(py_exe), "-0p"], ok(output))
        result = discover_interpreters(
            runner, str(self.dir_a), [".exe"], py_path=str(py_exe)
        )
        self.assertEqual(len(result.interpreters), 1)
        item = result.interpreters[0]
        self.assertIn("py-launcher", item.sources)
        self.assertIn("PATH", item.sources)
        self.assertEqual(item.version, "3.12.1")
        self.assertTrue(any("does not exist" in note for note in result.notes))

    def test_uv_output_parsed(self):
        python = make_exec(self.dir_a, "python.exe")
        uv_exe = make_exec(self.root / "bin", "uv.exe")
        output = (
            f"cpython-3.12.1-windows-x86_64-none       {python}\n"
            f"cpython-3.11.9-windows-x86_64-none       {self.root}\\other\\python.exe\n"
        )
        runner = FakeRunner()
        runner.add([str(python), "-c"], ok(interpreter_json(version="3.12.1")))
        runner.add(
            [str(uv_exe), "python", "list", "--only-installed"],
            ok(output),
        )
        result = discover_interpreters(runner, "", [".exe"], uv_path=str(uv_exe))
        self.assertEqual(len(result.interpreters), 1)
        self.assertIn("uv", result.interpreters[0].sources)
        self.assertTrue(any("does not exist" in note for note in result.notes))

    def test_uv_output_with_spaces_in_path(self):
        spaced_dir = self.root / "Program Files"
        spaced_dir.mkdir()
        python = make_exec(spaced_dir, "python.exe")
        uv_exe = make_exec(self.root / "bin", "uv.exe")
        output = f"cpython-3.12.1-windows-x86_64-none       {python}\n"
        runner = FakeRunner()
        runner.add([str(python), "-c"], ok(interpreter_json(version="3.12.1")))
        runner.add([str(uv_exe), "python", "list", "--only-installed"], ok(output))
        result = discover_interpreters(runner, "", [".exe"], uv_path=str(uv_exe))
        self.assertEqual(len(result.interpreters), 1)

    def test_manager_failure_produces_note(self):
        py_exe = make_exec(self.root / "bin", "py.exe")
        runner = FakeRunner()
        runner.add([str(py_exe), "-0p"], fail("exit-1"))
        result = discover_interpreters(runner, "", [".exe"], py_path=str(py_exe))
        self.assertTrue(any("query failed" in note for note in result.notes))

    def test_dedupe_via_symlink(self):
        python = make_exec(self.dir_a, "python.exe")
        dir_b = self.root / "b"
        dir_b.mkdir()
        try:
            os.symlink(python, dir_b / "python3.exe")
        except OSError:
            self.skipTest("symlinks are not available on this platform")
        runner = FakeRunner()
        runner.add([str(python), "-c"], ok(interpreter_json(version="3.12.1")))
        path_var = os.pathsep.join([str(self.dir_a), str(dir_b)])
        result = discover_interpreters(runner, path_var, [".exe"])
        self.assertEqual(len(result.interpreters), 1)
        self.assertIn("python3", result.interpreters[0].aliases)

    def test_versioned_glob_finds_python3_x(self):
        versioned = make_exec(self.dir_a, "python3.12")
        runner = FakeRunner()
        runner.add([str(versioned), "-c"], ok(interpreter_json(version="3.12.4")))
        result = discover_interpreters(
            runner, str(self.dir_a), None, versioned_glob=True
        )
        names = [Path(item.path).name for item in result.interpreters]
        self.assertIn("python3.12", names)

    def test_empty_path_finds_nothing(self):
        result = discover_interpreters(FakeRunner(), "", [".exe"])
        self.assertEqual(result.interpreters, ())
        self.assertEqual(result.notes, ())


if __name__ == "__main__":
    unittest.main()
