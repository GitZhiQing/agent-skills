from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

helpers.setup_env()


def run_cli(args, cwd: Path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(helpers.SRC) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "disk_cleanup"] + list(args),
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )


class CliTests(unittest.TestCase):
    def test_version_and_rules_check(self):
        proc = run_cli(["--version"], helpers.SKILL_ROOT)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("windows-disk-cleanup", proc.stdout)
        proc = run_cli(["rules", "--check", "--json"], helpers.SKILL_ROOT)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertTrue(data["ok"])
        self.assertGreaterEqual(data["count"], 200)

    def test_scan_delete_roundtrip(self):
        with tempfile.TemporaryDirectory(prefix="wdc-cli-") as tmp:
            tmp_path = Path(tmp)
            root = helpers.make_fixture(tmp_path / "fixture")
            out = tmp_path / "out"
            proc = run_cli(
                [
                    "scan",
                    "--root",
                    str(root),
                    "--output-dir",
                    str(out),
                    "--min-size",
                    "0",
                    "--json",
                ],
                helpers.SKILL_ROOT,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(Path(payload["report"]).exists())
            scan = json.loads((out / "scan.json").read_text(encoding="utf-8"))
            paths = [
                helpers.entry_by_suffix(scan, "AppData\\Local\\Temp")["path"],
                helpers.entry_by_suffix(scan, "node_modules")["path"],
            ]
            selection = helpers.write_selection(out, scan, paths)

            dry = run_cli(
                ["delete", "--selection", str(selection), "--dry-run", "--json"],
                helpers.SKILL_ROOT,
            )
            self.assertEqual(dry.returncode, 0, dry.stderr)
            plan = json.loads(dry.stdout)
            self.assertTrue(plan["ok"])
            self.assertEqual(len(plan["planned"]), 2)

            execute = run_cli(
                ["delete", "--selection", str(selection), "--yes", "--json"],
                helpers.SKILL_ROOT,
            )
            self.assertEqual(execute.returncode, 0, execute.stderr)
            result = json.loads(execute.stdout)
            self.assertTrue(result["ok"])
            self.assertEqual(result["summary"]["deleted"], 2)
            self.assertTrue(Path(result["cleanup_report"]).exists())
            for path in paths:
                self.assertFalse(Path(path).exists())

    def test_scan_delete_roundtrip_schema2_modes(self):
        with tempfile.TemporaryDirectory(prefix="wdc-cli-") as tmp:
            tmp_path = Path(tmp)
            root = helpers.make_fixture(tmp_path / "fixture")
            out = tmp_path / "out"
            proc = run_cli(
                [
                    "scan",
                    "--root",
                    str(root),
                    "--output-dir",
                    str(out),
                    "--min-size",
                    "0",
                    "--json",
                ],
                helpers.SKILL_ROOT,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            scan = json.loads((out / "scan.json").read_text(encoding="utf-8"))
            temp = helpers.entry_by_suffix(scan, "AppData\\Local\\Temp")["path"]
            modules = helpers.entry_by_suffix(scan, "node_modules")["path"]
            selection = helpers.write_selection(
                out, scan, [temp, modules],
                mode="permanent", schema=2, modes={temp: "recycle"},
            )

            dry = run_cli(
                ["delete", "--selection", str(selection), "--dry-run", "--json"],
                helpers.SKILL_ROOT,
            )
            self.assertEqual(dry.returncode, 0, dry.stderr)
            plan = json.loads(dry.stdout)
            self.assertTrue(plan["ok"])
            self.assertEqual(plan["modes"], {"recycle": 1, "permanent": 1})
            modes_by_path = {item["path"]: item["mode"] for item in plan["planned"]}
            self.assertEqual(modes_by_path[temp], "recycle")
            self.assertEqual(modes_by_path[modules], "permanent")

            execute = run_cli(
                ["delete", "--selection", str(selection), "--yes", "--json"],
                helpers.SKILL_ROOT,
            )
            self.assertIn(execute.returncode, (0, 1), execute.stderr)
            result = json.loads(execute.stdout)
            # 回收站在受限环境可能失败（见 memory L-005），只断言方式字段贯穿执行结果。
            item_modes = {item["path"]: item["mode"] for item in result["items"]}
            self.assertEqual(item_modes[temp], "recycle")
            self.assertEqual(item_modes[modules], "permanent")
            self.assertFalse(Path(modules).exists())

    def test_review_requires_allow_review(self):
        with tempfile.TemporaryDirectory(prefix="wdc-cli-") as tmp:
            tmp_path = Path(tmp)
            root = helpers.make_fixture(tmp_path / "fixture")
            out = tmp_path / "out"
            proc = run_cli(
                ["scan", "--root", str(root), "--output-dir", str(out), "--min-size", "0", "--json"],
                helpers.SKILL_ROOT,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            scan = json.loads((out / "scan.json").read_text(encoding="utf-8"))
            big = helpers.entry_by_suffix(scan, "big")["path"]
            selection = helpers.write_selection(out, scan, [big])
            proc = run_cli(
                ["delete", "--selection", str(selection), "--yes", "--json"],
                helpers.SKILL_ROOT,
            )
            self.assertEqual(proc.returncode, 2, proc.stderr)
            data = json.loads(proc.stdout)
            self.assertFalse(data["ok"])
            self.assertIn("allow-review", data["error"]["message"])

    def test_invalid_selection_and_missing_root(self):
        with tempfile.TemporaryDirectory(prefix="wdc-cli-") as tmp:
            tmp_path = Path(tmp)
            root = helpers.make_fixture(tmp_path / "fixture")
            out = tmp_path / "out"
            proc = run_cli(
                ["scan", "--root", str(root), "--output-dir", str(out), "--min-size", "0", "--json"],
                helpers.SKILL_ROOT,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            scan = json.loads((out / "scan.json").read_text(encoding="utf-8"))
            selection = helpers.write_selection(out, scan, [str(root / "not-in-scan")])
            proc = run_cli(
                ["delete", "--selection", str(selection), "--dry-run", "--json"],
                helpers.SKILL_ROOT,
            )
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertFalse(json.loads(proc.stdout)["ok"])

            proc = run_cli(
                ["scan", "--root", str(tmp_path / "missing"), "--output-dir", str(tmp_path / "o2"), "--json"],
                helpers.SKILL_ROOT,
            )
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertFalse(json.loads(proc.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()
