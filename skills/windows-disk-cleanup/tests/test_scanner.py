from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import helpers

helpers.setup_env()

from disk_cleanup.scanner import ScanOptions, Scanner


class ScannerTests(unittest.TestCase):
    def test_scan_fixture_classification_and_leaf_caches(self):
        with tempfile.TemporaryDirectory(prefix="wdc-scan-") as tmp:
            root = helpers.make_fixture(Path(tmp) / "fixture")
            result = helpers.scan_fixture(root)
            by = {e.path: e for e in result.entries}

            temp = by[str(root / "Users/alice/AppData/Local/Temp")]
            self.assertEqual(temp.recommendation, "safe")
            self.assertEqual(temp.size, 100)
            self.assertEqual(temp.files, 1)
            self.assertFalse(any("Temp" in p and p.endswith("a.txt") for p in by))

            modules = by[str(root / "proj/node_modules")]
            self.assertEqual(modules.recommendation, "safe")
            self.assertEqual(modules.size, 500)
            self.assertFalse(any("node_modules\\pkg" in p or "node_modules/pkg" in p for p in by))

            venv = by[str(root / "proj/.venv")]
            self.assertEqual(venv.recommendation, "safe")
            self.assertFalse(any(p.endswith("pyvenv.cfg") for p in by))

            downloads = by[str(root / "Users/alice/Downloads")]
            self.assertEqual(downloads.recommendation, "caution")
            self.assertEqual(downloads.role, "data")

            documents = by[str(root / "Users/alice/Documents")]
            self.assertEqual(documents.recommendation, "keep")
            self.assertFalse(documents.selectable)

            proj = by[str(root / "proj")]
            self.assertEqual(proj.size, 540)
            self.assertTrue(proj.is_top_level)

            self.assertEqual(result.stats.files, 9)
            self.assertEqual(result.stats.bytes, 2_098_742)
            self.assertFalse(result.stats.partial)
            self.assertEqual(result.omitted_entries, 0)

    def test_min_size_filters_generic_large_entries_but_keeps_rules(self):
        with tempfile.TemporaryDirectory(prefix="wdc-scan-") as tmp:
            root = helpers.make_fixture(Path(tmp) / "fixture")
            result = helpers.scan_fixture(root, min_size=1024 * 1024)
            paths = {e.path for e in result.entries}
            self.assertIn(str(root / "big"), paths)
            self.assertIn(str(root / "proj/node_modules"), paths)
            self.assertNotIn(str(root / "proj/src"), paths)
            # Top-level overview is always present, even below the threshold.
            self.assertIn(str(root / "proj"), paths)

    def test_exclude_skips_subtree(self):
        with tempfile.TemporaryDirectory(prefix="wdc-scan-") as tmp:
            root = helpers.make_fixture(Path(tmp) / "fixture")
            result = helpers.scan_fixture(root, exclude=["node_modules"])
            paths = {e.path for e in result.entries}
            self.assertNotIn(str(root / "proj/node_modules"), paths)
            proj = next(e for e in result.entries if e.path == str(root / "proj"))
            self.assertEqual(proj.size, 40)
            self.assertGreaterEqual(result.stats.excluded, 1)

    @unittest.skipUnless(os.name == "nt", "junction test requires Windows")
    def test_junction_is_not_followed(self):
        with tempfile.TemporaryDirectory(prefix="wdc-scan-") as tmp:
            root = helpers.make_fixture(Path(tmp) / "fixture")
            link = root / "big-link"
            proc = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(root / "big")],
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                self.skipTest("mklink /J unavailable: " + (proc.stderr or proc.stdout))
            try:
                result = helpers.scan_fixture(root)
                by = {e.path: e for e in result.entries}
                entry = by[str(link)]
                self.assertTrue(entry.reparse)
                self.assertFalse(entry.selectable)
                self.assertEqual(result.stats.bytes, 2_098_742)
            finally:
                try:
                    os.rmdir(link)
                except OSError:
                    pass

    def test_time_limit_marks_partial(self):
        with tempfile.TemporaryDirectory(prefix="wdc-scan-") as tmp:
            root = helpers.make_fixture(Path(tmp) / "fixture")
            options = ScanOptions(
                root=str(root),
                output_dir=str(Path(tmp) / "out"),
                min_size=0,
                max_seconds=1e-9,
            )
            result = Scanner(options).scan()
            self.assertTrue(result.stats.partial)


if __name__ == "__main__":
    unittest.main()
