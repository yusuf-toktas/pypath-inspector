"""Tests for sensitive path redaction in exported reports."""

from __future__ import annotations

import os
import unittest

from pypath_inspector.redaction import default_home, redact_text, redact_value


class RedactTextTest(unittest.TestCase):
    def test_home_replaced_with_tilde(self):
        home = os.path.join("C:", "Users", "alice")
        text = os.path.join(home, "AppData", "Local", "x")
        self.assertEqual(redact_text(text, home), os.path.join("~", "AppData", "Local", "x"))

    def test_exact_home_replaced(self):
        self.assertEqual(redact_text("C:\\Users\\alice", "C:\\Users\\alice"), "~")

    def test_no_match_untouched(self):
        self.assertEqual(redact_text("C:\\Program Files\\Python", "C:\\Users\\alice"),
                         "C:\\Program Files\\Python")

    def test_empty_inputs(self):
        self.assertEqual(redact_text("anything", ""), "anything")
        self.assertEqual(redact_text("", "C:\\Users\\alice"), "")

    def test_multiple_occurrences(self):
        home = "/home/alice"
        text = "/home/alice/bin:/home/alice/.local/bin"
        self.assertEqual(redact_text(text, home), "~/bin:~/.local/bin")

    def test_forward_slash_variant(self):
        home = "C:\\Users\\alice"
        self.assertEqual(redact_text("C:/Users/alice/scripts", home), "~/scripts")

    def test_case_insensitive_on_windows(self):
        if os.name != "nt":
            self.skipTest("Windows case-insensitive redaction")
        self.assertEqual(redact_text("C:\\USERS\\ALICE\\x", "C:\\Users\\alice"), "~\\x")

    def test_prefix_boundary_not_confused(self):
        home = "C:\\Users\\alice"
        self.assertEqual(redact_text("C:\\Users\\alice2\\x", home), "C:\\Users\\alice2\\x")


class RedactValueTest(unittest.TestCase):
    def test_nested_structures(self):
        home = "/home/alice"
        data = {
            "path": "/home/alice/venv/bin/python",
            "items": ["/home/alice/a", "/opt/b"],
            "nested": {"deep": "/home/alice/c"},
            "count": 3,
            "flag": True,
        }
        result = redact_value(data, home)
        self.assertEqual(result["path"], "~/venv/bin/python")
        self.assertEqual(result["items"], ["~/a", "/opt/b"])
        self.assertEqual(result["nested"]["deep"], "~/c")
        self.assertEqual(result["count"], 3)
        self.assertTrue(result["flag"])

    def test_original_not_mutated(self):
        home = "/home/alice"
        data = {"path": "/home/alice/x"}
        redact_value(data, home)
        self.assertEqual(data["path"], "/home/alice/x")

    def test_default_home_is_a_directory(self):
        self.assertTrue(os.path.isdir(default_home()))


if __name__ == "__main__":
    unittest.main()
