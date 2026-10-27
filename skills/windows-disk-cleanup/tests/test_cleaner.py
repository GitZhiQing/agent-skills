from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import helpers

helpers.setup_env()

from disk_cleanup.cleaner import execute_cleanup
from disk_cleanup.selection import (
    Selection,
    load_scan,
    load_selection,
    validate_selection,
)


class CleanerTests(unittest.TestCase):
    def _fixture_scan(self, tmp: Path):
        root = helpers.make_fixture(tmp / "fixture")
        out = tmp / "out"
        scan = helpers.scan_fixture(root, output_dir=out)
        helpers.write_scan(scan, out)
        scan_dict = json.loads((out / "scan.json").read_text(encoding="utf-8"))
        return root, out, scan_dict

    def test_validate_and_permanent_delete(self):
        with tempfile.TemporaryDirectory(prefix="wdc-del-") as tmp:
            root, out, scan = self._fixture_scan(Path(tmp))
            paths = [
                helpers.entry_by_suffix(scan, "AppData\\Local\\Temp")["path"],
                helpers.entry_by_suffix(scan, "node_modules")["path"],
            ]
            selection_file = helpers.write_selection(out, scan, paths)
            selection = load_selection(str(selection_file))
            validation = validate_selection(load_scan(str(out / "scan.json")), selection)
            self.assertEqual(validation.invalid, [])
            self.assertEqual(len(validation.planned), 2)
            self.assertEqual(validation.estimated_bytes, 600)

            result, outputs = execute_cleanup(
                scan, validation, str(out), confirmed=True, rules_version="test"
            )
            self.assertEqual(result.summary()["deleted"], 2)
            self.assertEqual(result.summary()["failed"], 0)
            for path in paths:
                self.assertFalse(Path(path).exists(), path)
            self.assertTrue(Path(outputs["cleanup_html"]).exists())
            self.assertTrue(Path(outputs["cleanup_json"]).exists())

    def test_protected_path_is_rejected_even_if_scan_forged(self):
        scan = {
            "schema": 1,
            "scan_id": "forged",
            "root": "C:\\",
            "entries": [
                {
                    "path": r"C:\Windows\System32",
                    "selectable": True,
                    "recommendation": "safe",
                    "size": 1,
                    "title": "forged",
                    "category": "forged",
                }
            ],
        }
        selection = Selection(
            scan_id="forged",
            paths=[r"C:\Windows\System32"],
            mode="permanent",
            confirmed=True,
        )
        validation = validate_selection(scan, selection)
        self.assertEqual(validation.planned, [])
        self.assertEqual(len(validation.invalid), 1)
        self.assertIn("Windows", validation.invalid[0]["reason"])

    def test_outside_root_and_unknown_path_are_rejected(self):
        scan = {
            "schema": 1,
            "scan_id": "scope",
            "root": r"C:\Temp",
            "entries": [
                {
                    "path": r"C:\Windows\Temp",
                    "selectable": True,
                    "recommendation": "safe",
                    "size": 1,
                }
            ],
        }
        selection = Selection(
            scan_id="scope",
            paths=[r"C:\Windows\Temp", r"C:\Temp\not-in-scan"],
            mode="permanent",
            confirmed=True,
        )
        validation = validate_selection(scan, selection)
        self.assertEqual(len(validation.invalid), 2)
        reasons = " ".join(item["reason"] for item in validation.invalid)
        self.assertIn("不在本次扫描根目录内", reasons)
        self.assertIn("不在本次扫描结果中", reasons)

    def test_keep_entry_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="wdc-del-") as tmp:
            root, out, scan = self._fixture_scan(Path(tmp))
            documents = helpers.entry_by_suffix(scan, "Documents")["path"]
            selection = Selection(
                scan_id=scan["scan_id"],
                paths=[documents],
                mode="permanent",
                confirmed=True,
            )
            validation = validate_selection(scan, selection)
            self.assertEqual(validation.planned, [])
            self.assertEqual(len(validation.invalid), 1)

    def test_review_requires_allow_review(self):
        with tempfile.TemporaryDirectory(prefix="wdc-del-") as tmp:
            root, out, scan = self._fixture_scan(Path(tmp))
            big = helpers.entry_by_suffix(scan, "big")["path"]
            selection = Selection(
                scan_id=scan["scan_id"],
                paths=[big],
                mode="permanent",
                confirmed=True,
            )
            validation = validate_selection(scan, selection)
            self.assertTrue(validation.requires_allow_review)
            self.assertIn(big, validation.review)

    def test_parent_covers_child(self):
        with tempfile.TemporaryDirectory(prefix="wdc-del-") as tmp:
            root, out, scan = self._fixture_scan(Path(tmp))
            parent = helpers.entry_by_suffix(scan, "proj")["path"]
            child = helpers.entry_by_suffix(scan, "node_modules")["path"]
            selection = Selection(
                scan_id=scan["scan_id"],
                paths=[child, parent],
                mode="permanent",
                confirmed=True,
            )
            validation = validate_selection(scan, selection)
            planned = [item["path"] for item in validation.planned]
            self.assertEqual(planned, [parent])
            self.assertEqual(len(validation.covered), 1)
            self.assertEqual(validation.covered[0]["path"], child)
            self.assertEqual(validation.estimated_bytes, 540)

    def test_missing_path_is_planned_but_skipped(self):
        with tempfile.TemporaryDirectory(prefix="wdc-del-") as tmp:
            root, out, scan = self._fixture_scan(Path(tmp))
            target = helpers.entry_by_suffix(scan, "node_modules")["path"]
            shutil.rmtree(target)
            selection = Selection(
                scan_id=scan["scan_id"],
                paths=[target],
                mode="permanent",
                confirmed=True,
            )
            validation = validate_selection(scan, selection)
            self.assertEqual(len(validation.missing), 1)
            result, _ = execute_cleanup(scan, validation, str(out), confirmed=True)
            self.assertEqual(result.items[0].status, "skipped_missing")
            self.assertEqual(result.summary()["deleted"], 0)


if __name__ == "__main__":
    unittest.main()
