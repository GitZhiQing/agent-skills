from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import helpers

helpers.setup_env()

from disk_cleanup.cleaner import execute_cleanup
from disk_cleanup.selection import (
    Selection,
    SelectionError,
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

    def test_schema2_per_path_modes_validate_and_execute(self):
        with tempfile.TemporaryDirectory(prefix="wdc-del-") as tmp:
            root, out, scan = self._fixture_scan(Path(tmp))
            temp = helpers.entry_by_suffix(scan, "AppData\\Local\\Temp")["path"]
            modules = helpers.entry_by_suffix(scan, "node_modules")["path"]
            selection_file = helpers.write_selection(
                out, scan, [temp, modules],
                mode="permanent", schema=2,
                modes={temp: "recycle", r"C:\not\selected": "permanent"},
            )
            selection = load_selection(str(selection_file))
            self.assertEqual(selection.schema, 2)
            validation = validate_selection(load_scan(str(out / "scan.json")), selection)
            self.assertEqual(validation.invalid, [])
            by_path = {item["path"]: item for item in validation.planned}
            self.assertEqual(by_path[temp]["mode"], "recycle")
            self.assertEqual(by_path[modules]["mode"], "permanent")
            self.assertEqual(validation.mode_counts, {"recycle": 1, "permanent": 1})

            with unittest.mock.patch(
                "disk_cleanup.cleaner.recycle_paths",
                return_value=[{"path": temp, "ok": True}],
            ) as mock_recycle:
                result, outputs = execute_cleanup(
                    scan, validation, str(out), confirmed=True, rules_version="test"
                )
            mock_recycle.assert_called_once()
            self.assertEqual(mock_recycle.call_args[0][0], [temp])
            statuses = {item.path: item.status for item in result.items}
            self.assertEqual(statuses[temp], "moved_to_recycle_bin")
            self.assertEqual(statuses[modules], "deleted")
            modes_in_json = {item["path"]: item["mode"] for item in json.loads(
                Path(outputs["cleanup_json"]).read_text(encoding="utf-8")
            )["items"]}
            self.assertEqual(modes_in_json[temp], "recycle")
            self.assertEqual(modes_in_json[modules], "permanent")

    def test_schema1_stays_global_mode(self):
        with tempfile.TemporaryDirectory(prefix="wdc-del-") as tmp:
            root, out, scan = self._fixture_scan(Path(tmp))
            temp = helpers.entry_by_suffix(scan, "AppData\\Local\\Temp")["path"]
            selection_file = helpers.write_selection(out, scan, [temp], mode="recycle")
            selection = load_selection(str(selection_file))
            self.assertEqual(selection.schema, 1)
            self.assertEqual(selection.modes, {})
            validation = validate_selection(load_scan(str(out / "scan.json")), selection)
            self.assertEqual(validation.planned[0]["mode"], "recycle")

    def test_mode_override_beats_per_path_modes(self):
        with tempfile.TemporaryDirectory(prefix="wdc-del-") as tmp:
            root, out, scan = self._fixture_scan(Path(tmp))
            temp = helpers.entry_by_suffix(scan, "AppData\\Local\\Temp")["path"]
            selection_file = helpers.write_selection(
                out, scan, [temp], mode="recycle", schema=2, modes={temp: "recycle"},
            )
            selection = load_selection(str(selection_file))
            validation = validate_selection(
                load_scan(str(out / "scan.json")), selection, mode_override="permanent"
            )
            self.assertEqual(validation.planned[0]["mode"], "permanent")

    def test_illegal_mode_value_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="wdc-del-") as tmp:
            root, out, scan = self._fixture_scan(Path(tmp))
            temp = helpers.entry_by_suffix(scan, "AppData\\Local\\Temp")["path"]
            selection_file = helpers.write_selection(
                out, scan, [temp], schema=2, modes={temp: "burn"},
            )
            with self.assertRaises(SelectionError) as ctx:
                load_selection(str(selection_file))
            self.assertIn("删除方式非法", str(ctx.exception))

    def test_unsupported_schema_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="wdc-del-") as tmp:
            root, out, scan = self._fixture_scan(Path(tmp))
            temp = helpers.entry_by_suffix(scan, "AppData\\Local\\Temp")["path"]
            selection_file = helpers.write_selection(out, scan, [temp], schema=3)
            with self.assertRaises(SelectionError) as ctx:
                load_selection(str(selection_file))
            self.assertIn("schema", str(ctx.exception))

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
