from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import memory  # noqa: E402


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wdc-memory-")
        self.root = Path(self.tmp.name) / "memory"

    def tearDown(self):
        self.tmp.cleanup()

    def record(self, **overrides):
        values = {
            "kind": "failure",
            "scope": "delete",
            "triggers": ["access denied", "locked"],
            "finding": "删除时遇到 Access denied。",
            "action": "提示管理员重跑；不停止服务、不改 ACL。",
            "title": "权限失败先提示管理员",
            "privacy": "public",
            "rule_ids": ["win-temp"],
            "error_types": ["PermissionError"],
        }
        values.update(overrides)
        return memory.record(self.root, **values)

    def test_record_search_used_graduate(self):
        lesson = self.record()
        self.assertEqual(lesson["id"], "L-001")
        self.assertTrue((self.root / "lessons" / lesson["_file"]).exists())
        index = (self.root / "INDEX.md").read_text(encoding="utf-8")
        self.assertIn("L-001", index)

        results = memory.search(self.root, "access denied")
        self.assertEqual([item["id"] for item in results], ["L-001"])

        for _ in range(3):
            memory.mark_used(self.root, "L-001")
        item = memory.load_lessons(self.root, "public")[0]
        self.assertEqual(item["used"], 3)
        self.assertEqual(item["status"], "candidate")

        memory.graduate(self.root, "L-001", "rules.json#win-temp", "已写入规则")
        item = memory.load_lessons(self.root, "public")[0]
        self.assertEqual(item["status"], "graduated")
        self.assertEqual(item["graduated_to"], "rules.json#win-temp")
        self.assertEqual(memory.search(self.root, "access denied"), [])
        self.assertEqual(
            [x["id"] for x in memory.search(self.root, "access denied", all_status=True)],
            ["L-001"],
        )
        self.assertTrue(memory.validate(self.root)["ok"])

    def test_public_sanitizes_user_paths(self):
        lesson = self.record(
            finding=r"扫描 C:\Users\alice\AppData\Local\Temp 时发现权限问题。",
            action="只记录规则和错误类型。",
        )
        text = json.dumps(lesson, ensure_ascii=False)
        self.assertNotIn("alice", text)
        self.assertIn("<user>", text)

    def test_public_rejects_secrets(self):
        with self.assertRaises(memory.MemoryStoreError):
            self.record(finding="password=hunter2", action="不要记录这个值。")
        self.assertFalse((self.root / "lessons").exists() and list((self.root / "lessons").glob("*.json")))

    def test_local_layer_preserves_paths_and_is_separate(self):
        lesson = self.record(
            privacy="local",
            finding=r"删除 C:\Users\alice\Downloads\old.zip 失败。",
            action="检查文件占用。",
        )
        self.assertEqual(lesson["id"], "P-001")
        local_file = self.root / "local" / "lessons" / lesson["_file"]
        self.assertTrue(local_file.exists())
        self.assertIn("alice", local_file.read_text(encoding="utf-8"))
        public_index = self.root / "INDEX.md"
        self.assertFalse(public_index.exists())
        self.assertEqual(
            [x["id"] for x in memory.search(self.root, "old.zip", privacy="local")],
            ["P-001"],
        )
        self.assertTrue(memory.validate(self.root)["ok"])

    def test_validate_detects_missing_fields_and_duplicate_ids(self):
        self.record()
        bad = self.root / "lessons" / "L-999-bad.json"
        bad.write_text(json.dumps({"schema": 1, "id": "L-999"}), encoding="utf-8")
        result = memory.validate(self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any("title" in error or "kind" in error for error in result["errors"]))
        duplicate = self.root / "lessons" / "L-001-duplicate.json"
        # Duplicate ID via a second file with the same id.
        original = memory.load_lessons(self.root, "public")[0]
        data = json.loads((self.root / "lessons" / original["_file"]).read_text(encoding="utf-8"))
        duplicate.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = memory.validate(self.root)
        self.assertTrue(any("id 重复" in error for error in result["errors"]))

    def test_public_unmasked_path_is_flagged(self):
        directory = self.root / "lessons"
        directory.mkdir(parents=True)
        data = {
            "schema": 1,
            "id": "L-001",
            "title": "bad",
            "kind": "failure",
            "scope": "delete",
            "trigger": ["x"],
            "finding": r"C:\Users\alice\Downloads\old.zip",
            "action": "x",
            "evidence": {"rule_ids": [], "error_types": [], "options": {}, "notes": ""},
            "used": 0,
            "status": "active",
            "privacy": "public",
        }
        (directory / "L-001-bad.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = memory.validate(self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any("未脱敏" in error for error in result["errors"]))

    def test_graduate_requires_target(self):
        self.record()
        with self.assertRaises(memory.MemoryUsageError):
            memory.graduate(self.root, "L-001", "")

    def test_index_lists_status_counts(self):
        self.record()
        index = (self.root / "INDEX.md").read_text(encoding="utf-8")
        self.assertIn("active 1", index)
        memory.mark_used(self.root, "L-001")
        index = (self.root / "INDEX.md").read_text(encoding="utf-8")
        self.assertIn("| 1 | active |", index)


if __name__ == "__main__":
    unittest.main()
