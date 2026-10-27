from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import helpers

helpers.setup_env()

from disk_cleanup.rules import RuleIndex, load_rules, validate_rules


class RuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_rules()
        cls.index = RuleIndex(cls.data["rules"], "C:\\")

    def test_catalog_is_valid_and_large(self):
        self.assertEqual(validate_rules(self.data), [])
        self.assertGreaterEqual(len(self.data["rules"]), 200)
        ids = [rule["id"] for rule in self.data["rules"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_exact_and_suffix_matches(self):
        self.assertEqual(self.index.match(r"C:\Windows.old")["id"], "sys-windows-old")
        self.assertEqual(self.index.match(r"C:\Windows\Temp")["id"], "win-temp")
        self.assertEqual(
            self.index.match(r"C:\Users\alice\AppData\Local\Temp")["id"], "user-temp"
        )
        self.assertEqual(self.index.match(r"C:\Users\alice\Downloads")["id"], "user-downloads")

    def test_project_basename_matches(self):
        self.assertEqual(self.index.match(r"D:\proj\node_modules")["id"], "dev-node-modules")
        self.assertEqual(self.index.match(r"D:\proj\__pycache__")["id"], "dev-pycache")

    def test_venv_requires_pyvenv_cfg(self):
        with tempfile.TemporaryDirectory() as tmp:
            venv = Path(tmp) / ".venv"
            venv.mkdir()
            self.assertIsNone(self.index.match(str(venv)))
            (venv / "pyvenv.cfg").write_text("home = python", encoding="utf-8")
            self.index._dir_names_cache.clear()
            rule = self.index.match(str(venv))
            self.assertIsNotNone(rule)
            self.assertEqual(rule["id"], "dev-venv")

    def test_dist_requires_project_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "proj"
            dist = project / "dist"
            dist.mkdir(parents=True)
            self.assertIsNone(self.index.match(str(dist)))
            (project / "package.json").write_text("{}", encoding="utf-8")
            self.index._dir_names_cache.clear()
            rule = self.index.match(str(dist))
            self.assertIsNotNone(rule)
            self.assertEqual(rule["id"], "dev-dist")
            self.assertEqual(rule["recommendation"], "caution")

    def test_secrets_and_git_are_keep(self):
        for name in (".git", ".ssh", ".gnupg", ".aws", ".kube"):
            rule = self.index.match(str(Path("D:/proj") / name))
            self.assertIsNotNone(rule, name)
            self.assertEqual(rule["recommendation"], "keep", name)
            self.assertEqual(rule["mode"], "skip", name)

    def test_project_caches_are_not_matched_inside_program_files(self):
        self.assertIsNone(self.index.match(r"C:\Program Files\SomeApp\node_modules"))
        self.assertIsNone(self.index.match(r"C:\Program Files\SomeApp\__pycache__"))

    def test_pruning_interest_set(self):
        self.assertTrue(self.index.has_interesting_below(r"C:\Windows"))
        self.assertTrue(self.index.has_interesting_below(r"C:\Windows\System32"))
        self.assertFalse(self.index.has_interesting_below(r"C:\Windows\WinSxS"))
        self.assertFalse(self.index.has_interesting_below(r"C:\Windows\System32\DriverStore"))
        self.assertFalse(self.index.has_interesting_below(r"C:\Program Files"))

    def test_file_hints(self):
        self.assertTrue(self.index.file_hint("pagefile.sys"))
        self.assertTrue(self.index.file_hint("hiberfil.sys"))
        self.assertTrue(self.index.file_hint("ext4.vhdx"))
        self.assertTrue(self.index.file_hint("docker_data.vhdx"))
        self.assertFalse(self.index.file_hint("random.txt"))


if __name__ == "__main__":
    unittest.main()
