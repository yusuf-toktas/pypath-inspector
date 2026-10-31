"""Tests for PATH resolution and duplicate PATH entry detection."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from pypath_inspector.resolution import (
    analyze_path,
    candidate_names,
    find_on_path,
    is_script_shim,
    normalize_entry,
    resolve_commands,
)

from .fakes import make_exec


class FindOnPathTest(unittest.TestCase):
    """PATH scanning with temporary directories."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.dir_a = self.root / "a"
        self.dir_b = self.root / "b"
        self.dir_a.mkdir()
        self.dir_b.mkdir()

    def test_first_match_wins_in_path_order(self):
        make_exec(self.dir_a, "python.exe")
        make_exec(self.dir_b, "python.exe")
        path_var = os.pathsep.join([str(self.dir_a), str(self.dir_b)])
        matches = find_on_path("python", path_var, [".exe"])
        self.assertEqual(len(matches), 2)
        self.assertEqual(Path(matches[0].path).parent, self.dir_a)
        self.assertEqual(Path(matches[1].path).parent, self.dir_b)

    def test_no_match(self):
        matches = find_on_path("python", str(self.dir_a), [".exe"])
        self.assertEqual(matches, [])

    def test_missing_directory_is_skipped(self):
        make_exec(self.dir_b, "python.exe")
        path_var = os.pathsep.join([str(self.root / "missing"), str(self.dir_b)])
        matches = find_on_path("python", path_var, [".exe"])
        self.assertEqual(len(matches), 1)

    def test_pathext_order_within_directory(self):
        make_exec(self.dir_a, "python.bat")
        make_exec(self.dir_a, "python.exe")
        matches = find_on_path("python", str(self.dir_a), [".bat", ".exe"])
        self.assertEqual(len(matches), 1)
        self.assertTrue(matches[0].path.endswith("python.bat"))
        matches = find_on_path("python", str(self.dir_a), [".exe", ".bat"])
        self.assertTrue(matches[0].path.endswith("python.exe"))

    def test_bare_name_without_pathext(self):
        make_exec(self.dir_a, "python")
        matches = find_on_path("python", str(self.dir_a), None)
        self.assertEqual(len(matches), 1)
        matches = find_on_path("python", str(self.dir_a), [])
        self.assertEqual(len(matches), 1)

    def test_non_executable_file_is_ignored_posix(self):
        if os.name == "nt":
            self.skipTest("POSIX executable-bit semantics")
        (self.dir_a / "python").write_text("", encoding="ascii")
        matches = find_on_path("python", str(self.dir_a), None)
        self.assertEqual(matches, [])

    def test_empty_entry_searches_current_directory(self):
        target = make_exec(self.dir_a, "python.exe")
        old_cwd = os.getcwd()
        os.chdir(self.dir_a)
        try:
            matches = find_on_path("python", "", [".exe"])
        finally:
            os.chdir(old_cwd)
        self.assertEqual(len(matches), 1)
        self.assertEqual(Path(matches[0].path).name, target.name)


class CandidateNamesTest(unittest.TestCase):
    """PATHEXT expansion rules."""

    def test_expansion(self):
        self.assertEqual(candidate_names("python", [".exe", ".bat"]), ["python.exe", "python.bat"])

    def test_existing_extension_is_kept(self):
        self.assertEqual(candidate_names("python.exe", [".exe", ".bat"]), ["python.exe"])

    def test_none_means_bare_name(self):
        self.assertEqual(candidate_names("python", None), ["python"])


class AnalyzePathTest(unittest.TestCase):
    """Duplicate, empty and missing PATH entry analysis."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.dir_a = self.root / "a"
        self.dir_a.mkdir()

    def test_duplicate_entries_detected(self):
        path_var = os.pathsep.join([str(self.dir_a), str(self.root / "b"), str(self.dir_a)])
        analysis = analyze_path(path_var)
        self.assertEqual(len(analysis.duplicate_groups), 1)
        group = analysis.duplicate_groups[0]
        self.assertEqual(group.count, 2)
        self.assertEqual(group.indices, (0, 2))

    def test_case_and_separator_variants_are_duplicates_on_windows(self):
        if os.name != "nt":
            self.skipTest("Windows case-insensitive normalisation")
        path_var = f"{self.dir_a};{str(self.dir_a).lower()}\\"
        analysis = analyze_path(path_var)
        self.assertEqual(len(analysis.duplicate_groups), 1)

    def test_empty_entries_counted(self):
        path_var = os.pathsep.join([str(self.dir_a), "", ""])
        analysis = analyze_path(path_var)
        self.assertEqual(analysis.empty_entries, 2)

    def test_missing_entries_reported(self):
        missing = str(self.root / "not-there")
        analysis = analyze_path(os.pathsep.join([str(self.dir_a), missing]))
        self.assertEqual(analysis.missing_entries, (missing,))

    def test_no_duplicates(self):
        analysis = analyze_path(str(self.dir_a))
        self.assertEqual(analysis.duplicate_groups, ())
        self.assertEqual(analysis.empty_entries, 0)


class ResolveCommandsTest(unittest.TestCase):
    """End-to-end command resolution."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.dir_a = self.root / "a"
        self.dir_a.mkdir()

    def test_resolution_report(self):
        exe = make_exec(self.dir_a, "python.exe")
        make_exec(self.dir_a, "pip.exe")
        path_var = str(self.dir_a)
        resolutions = resolve_commands(("python", "pip", "uv"), path_var, [".exe"])
        by_name = {item.name: item for item in resolutions}
        self.assertEqual(Path(by_name["python"].resolved), exe)
        self.assertIsNotNone(by_name["pip"].resolved)
        self.assertIsNone(by_name["uv"].resolved)

    def test_shadowed_command_has_multiple_matches(self):
        dir_b = self.root / "b"
        dir_b.mkdir()
        make_exec(self.dir_a, "python.exe")
        make_exec(dir_b, "python.exe")
        path_var = os.pathsep.join([str(self.dir_a), str(dir_b)])
        (resolution,) = resolve_commands(("python",), path_var, [".exe"])
        self.assertEqual(len(resolution.matches), 2)
        self.assertEqual(Path(resolution.resolved).parent, self.dir_a)


class HelpersTest(unittest.TestCase):
    def test_normalize_entry(self):
        self.assertEqual(normalize_entry("  "), "")
        self.assertTrue(normalize_entry("C:\\A\\"))

    def test_is_script_shim(self):
        self.assertTrue(is_script_shim(r"C:\x\python.bat"))
        self.assertFalse(is_script_shim(r"C:\x\python.exe"))


if __name__ == "__main__":
    unittest.main()
