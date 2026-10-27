from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import helpers

helpers.setup_env()

from disk_cleanup.model import (
    DeleteItem,
    DeleteResult,
    Entry,
    ScanResult,
    ScanStats,
)
from disk_cleanup.report import write_cleanup_outputs, write_scan_outputs


def sample_scan(root: str) -> ScanResult:
    entry = Entry(
        path=root.rstrip("/\\") + "\\cache",
        name="cache",
        kind="dir",
        role="cleanup",
        is_top_level=True,
        size=12345,
        files=3,
        dirs=1,
        size_known=True,
        title="测试缓存",
        category="测试",
        scope="user",
        description="说明 <script>alert(1)</script>",
        action="可以删除",
        risk="可重新生成",
        recommendation="safe",
        selectable=True,
        method="permanent",
        depth=1,
    )
    return ScanResult(
        schema=1,
        scan_id="scan-test-0001",
        root=root,
        root_display=root,
        output_dir="",
        started_at="2026-10-27T10:00:00+08:00",
        finished_at="2026-10-27T10:00:01+08:00",
        duration_s=1.0,
        volume={"total": 1000, "used": 500, "free": 500, "root": root, "label": "Test", "filesystem": "NTFS", "drive_type": "fixed"},
        environment={"platform": "nt", "admin": False, "python": "3.13", "drive_type": "fixed", "drive_type_label": "本地磁盘"},
        options={"min_size": 1, "listing_depth": 3, "max_entries": 1500, "max_seconds": 0, "exclude": []},
        stats=ScanStats(dirs=1, files=3, bytes=12345),
        entries=[entry],
        notes=["note"],
        rules_version="2026-10-27",
    )


class ReportTests(unittest.TestCase):
    def test_scan_report_is_standalone_and_escaped(self):
        with tempfile.TemporaryDirectory(prefix="wdc-report-") as tmp:
            out = Path(tmp) / "out"
            outputs = write_scan_outputs(sample_scan(r"C:\Temp"), str(out))
            html = Path(outputs["report_html"]).read_text(encoding="utf-8")
            self.assertIn("磁盘扫描报告", html)
            self.assertIn("scan-test-0001", html)
            self.assertIn("\\u003cscript", html)
            self.assertNotIn("__TITLE__", html)
            self.assertNotIn("/*__WINDOWS_DISK_CLEANUP_DATA__*/", html)
            self.assertNotIn("<script src=", html)
            self.assertTrue(Path(outputs["scan_json"]).exists())

    def test_cleanup_report_renders_statuses(self):
        with tempfile.TemporaryDirectory(prefix="wdc-report-") as tmp:
            out = Path(tmp) / "out"
            item = DeleteItem(
                path=r"C:\Temp\cache",
                title="测试缓存",
                category="测试",
                recommendation="safe",
                size=100,
                status="deleted",
                freed=100,
            )
            result = DeleteResult(
                schema=1,
                scan_id="scan-test-0001",
                root=r"C:\Temp",
                mode="permanent",
                started_at="2026-10-27T10:00:00+08:00",
                finished_at="2026-10-27T10:00:01+08:00",
                duration_s=1.0,
                dry_run=False,
                confirmed=True,
                volume_before={"total": 1000, "used": 500, "free": 500, "root": "C:/"},
                volume_after={"total": 1000, "used": 400, "free": 600, "root": "C:/"},
                items=[item],
                notes=["彻底删除不可恢复。"],
            )
            outputs = write_cleanup_outputs(result, str(out), r"C:\Temp", "2026-10-27")
            html = Path(outputs["cleanup_html"]).read_text(encoding="utf-8")
            self.assertIn("清理报告", html)
            self.assertIn("已删除", html)
            self.assertIn("测试缓存", html)
            self.assertIn("2026-10-27", html)
            self.assertNotIn("__TITLE__", html)
            self.assertTrue(Path(outputs["cleanup_json"]).exists())


if __name__ == "__main__":
    unittest.main()
