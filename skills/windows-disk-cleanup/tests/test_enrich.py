from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

helpers.setup_env()

from disk_cleanup.enrich import (
    EnrichError,
    load_enrichment,
    validate_enrichment,
    write_enriched_outputs,
)
from disk_cleanup.selection import Selection, validate_selection


def make_enrichment(scan: dict, path: str, **overrides) -> dict:
    entry = {
        "skill": "windows-disk-cleanup",
        "schema": 1,
        "scan_id": scan["scan_id"],
        "analyzer": "ai-agent",
        "entries": [
            {
                "path": path,
                "category": "游戏引擎缓存",
                "language": "",
                "title": "Unity 缓存",
                "description": "Unity 编辑器的可再生成缓存。",
                "advice": "safe",
                "confidence": "high",
                "evidence": ["Cache", "ShaderCache"],
            }
        ],
    }
    entry["entries"][0].update(overrides)
    return entry


class EnrichTests(unittest.TestCase):
    def _fixture(self, tmp: Path):
        root = helpers.make_fixture(tmp / "fixture")
        out = tmp / "out"
        scan = helpers.scan_fixture(root, output_dir=out)
        helpers.write_scan(scan, out)
        scan_dict = json.loads((out / "scan.json").read_text(encoding="utf-8"))
        return root, out, scan_dict

    def test_high_confidence_advice_retiers_review_entry(self):
        with tempfile.TemporaryDirectory(prefix="wdc-enr-") as tmp:
            root, out, scan = self._fixture(Path(tmp))
            target = helpers.entry_by_suffix(scan, "big")["path"]
            before = next(e for e in scan["entries"] if e["path"] == target)
            self.assertEqual(before["recommendation"], "review")
            enrichment = make_enrichment(scan, target)
            self.assertEqual(validate_enrichment(enrichment, scan), [])

            from disk_cleanup.enrich import apply_enrichment

            result, applied, retiered = apply_enrichment(scan, enrichment)
            self.assertEqual((applied, retiered), (1, 1))
            entry = next(e for e in result.entries if e.path == target)
            self.assertEqual(entry.title, "Unity 缓存")
            self.assertEqual(entry.category, "游戏引擎缓存")
            self.assertTrue(entry.enriched)
            # 高置信 AI 判定把「待定」提升为明确档位，并标注来源。
            self.assertEqual(entry.recommendation, "safe")
            self.assertEqual(entry.tier_source, "ai")
            self.assertTrue(entry.selectable)
            # 删除方式与其它非档位安全属性仍由规则决定。
            self.assertEqual(entry.method, before["method"])
            self.assertEqual(entry.requires_admin, before["requires_admin"])

    def test_ai_cannot_widen_or_downgrade_rule_tiers(self):
        with tempfile.TemporaryDirectory(prefix="wdc-enr-") as tmp:
            root, out, scan = self._fixture(Path(tmp))
            from disk_cleanup.enrich import apply_enrichment

            # 规则已定为 safe 的条目：AI 说 keep 也不能改档（只保留展示意见）。
            safe_path = helpers.entry_by_suffix(scan, "AppData\\Local\\Temp")["path"]
            scan_copy = json.loads(json.dumps(scan))
            result, applied, retiered = apply_enrichment(
                scan_copy, make_enrichment(scan, safe_path, advice="keep")
            )
            entry = next(e for e in result.entries if e.path == safe_path)
            self.assertEqual(entry.recommendation, "safe")
            self.assertEqual(entry.tier_source, "")
            self.assertTrue(entry.selectable)
            self.assertEqual(retiered, 0)

    def test_medium_confidence_advice_does_not_retier(self):
        with tempfile.TemporaryDirectory(prefix="wdc-enr-") as tmp:
            root, out, scan = self._fixture(Path(tmp))
            from disk_cleanup.enrich import apply_enrichment

            target = helpers.entry_by_suffix(scan, "big")["path"]
            result, applied, retiered = apply_enrichment(
                scan, make_enrichment(scan, target, confidence="medium")
            )
            entry = next(e for e in result.entries if e.path == target)
            self.assertEqual(entry.recommendation, "review")
            self.assertEqual(entry.advice, "safe")
            self.assertEqual(entry.tier_source, "")
            self.assertEqual(retiered, 0)

    def test_ai_keep_makes_review_entry_unselectable(self):
        with tempfile.TemporaryDirectory(prefix="wdc-enr-") as tmp:
            root, out, scan = self._fixture(Path(tmp))
            from disk_cleanup.enrich import apply_enrichment

            target = helpers.entry_by_suffix(scan, "big")["path"]
            result, applied, retiered = apply_enrichment(
                scan, make_enrichment(scan, target, advice="keep")
            )
            entry = next(e for e in result.entries if e.path == target)
            self.assertEqual(entry.recommendation, "keep")
            self.assertFalse(entry.selectable)
            self.assertEqual(retiered, 1)
            # 收紧是安全的：该条目在删除校验里会被拒绝。
            selection = Selection(scan_id=result.scan_id, paths=[target], mode="permanent", confirmed=True)
            validation = validate_selection(result.to_dict(), selection)
            self.assertEqual(validation.planned, [])
            self.assertEqual(len(validation.invalid), 1)

    def test_ai_suggest_is_rejected_by_validation(self):
        with tempfile.TemporaryDirectory(prefix="wdc-enr-") as tmp:
            root, out, scan = self._fixture(Path(tmp))
            target = helpers.entry_by_suffix(scan, "big")["path"]
            errs = validate_enrichment(make_enrichment(scan, target, advice="suggest"), scan)
            self.assertTrue(any("advice 非法" in e for e in errs))

    def test_rejects_unknown_path_and_bad_values(self):
        with tempfile.TemporaryDirectory(prefix="wdc-enr-") as tmp:
            root, out, scan = self._fixture(Path(tmp))
            bad = make_enrichment(scan, r"C:\not\in\scan")
            errs = validate_enrichment(bad, scan)
            self.assertTrue(any("不在扫描结果中" in e for e in errs))

            target = helpers.entry_by_suffix(scan, "big")["path"]
            errs = validate_enrichment(make_enrichment(scan, target, language="klingon"), scan)
            self.assertTrue(any("language 非法" in e for e in errs))
            errs = validate_enrichment(make_enrichment(scan, target, advice="suggest"), scan)
            self.assertTrue(any("advice 非法" in e for e in errs))
            errs = validate_enrichment(make_enrichment(scan, target, confidence="maybe"), scan)
            self.assertTrue(any("confidence 非法" in e for e in errs))

            mismatch = make_enrichment(scan, target)
            mismatch["scan_id"] = "other-scan"
            self.assertTrue(validate_enrichment(mismatch, scan))

    def test_entry_without_any_display_field_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="wdc-enr-") as tmp:
            root, out, scan = self._fixture(Path(tmp))
            target = helpers.entry_by_suffix(scan, "big")["path"]
            empty = make_enrichment(scan, target)
            empty["entries"][0] = {"path": target, "evidence": ["x"]}
            errs = validate_enrichment(empty, scan)
            self.assertTrue(any("至少要填一个展示字段" in e for e in errs))

    def test_load_enrichment_rejects_bad_schema(self):
        with tempfile.TemporaryDirectory(prefix="wdc-enr-") as tmp:
            p = Path(tmp) / "enrichment.json"
            p.write_text(json.dumps({"skill": "other-tool", "schema": 1, "scan_id": "x", "entries": [{}]}), encoding="utf-8")
            with self.assertRaises(EnrichError):
                load_enrichment(str(p))

    def test_write_enriched_outputs_renders_ai_badges(self):
        with tempfile.TemporaryDirectory(prefix="wdc-enr-") as tmp:
            root, out, scan = self._fixture(Path(tmp))
            target = helpers.entry_by_suffix(scan, "big")["path"]
            enrichment = make_enrichment(scan, target)
            enr_path = out / "enrichment.json"
            enr_path.write_text(json.dumps(enrichment, ensure_ascii=False, indent=2), encoding="utf-8")
            enriched_dir = out / "enriched"
            outputs = write_enriched_outputs(
                scan, enrichment, str(enriched_dir), enrichment_source=str(enr_path)
            )
            self.assertEqual(outputs["applied"], 1)
            html = Path(outputs["report_html"]).read_text(encoding="utf-8")
            self.assertIn("Unity 缓存", html)
            self.assertIn("AI 分析", html)
            self.assertIn("AI 定档", html)
            self.assertTrue((enriched_dir / "enrichment.json").exists())
            # 增强后的 scan.json：展示字段合并、档位由 AI 提升并标注来源。
            enriched_scan = json.loads((enriched_dir / "scan.json").read_text(encoding="utf-8"))
            entry = next(e for e in enriched_scan["entries"] if e["path"] == target)
            self.assertTrue(entry["enriched"])
            self.assertEqual(entry["advice"], "safe")
            self.assertEqual(entry["recommendation"], "safe")
            self.assertEqual(entry["tier_source"], "ai")
            # 分类三维随条目落盘，供报告页筛选。
            self.assertIn(entry["group"], ("system", "app", "dev", "user", "virtual"))
            self.assertIn(entry["nature"], ("cache", "log", "build", "installer", "temp", "content", "config", "other"))

    def test_cli_enrich_check_and_apply(self):
        with tempfile.TemporaryDirectory(prefix="wdc-enr-") as tmp:
            root, out, scan = self._fixture(Path(tmp))
            target = helpers.entry_by_suffix(scan, "big")["path"]
            enr = out / "enrichment.json"
            enr.write_text(json.dumps(make_enrichment(scan, target), ensure_ascii=False), encoding="utf-8")
            env = {
                **__import__("os").environ,
                "PYTHONPATH": str(helpers.SRC),
            }
            proc = subprocess.run(
                [sys.executable, "-m", "disk_cleanup", "enrich", "--scan", str(out / "scan.json"),
                 "--enrichment", str(enr), "--check", "--json"],
                capture_output=True, text=True, encoding="utf-8", env=env, timeout=120,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(json.loads(proc.stdout)["ok"])

            proc = subprocess.run(
                [sys.executable, "-m", "disk_cleanup", "enrich", "--scan", str(out / "scan.json"),
                 "--enrichment", str(enr), "--json"],
                capture_output=True, text=True, encoding="utf-8", env=env, timeout=120,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(proc.stdout)
            self.assertEqual(data["applied"], 1)
            self.assertTrue(Path(data["report"]).exists())


if __name__ == "__main__":
    unittest.main()
