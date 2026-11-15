from __future__ import annotations

import json
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

    def test_upgrade_leftovers_are_suggest(self):
        suggest_ids = {
            rule["id"]
            for rule in self.data["rules"]
            if rule.get("recommendation") == "suggest"
        }
        self.assertEqual(
            suggest_ids,
            {
                "sys-windows-old",
                "sys-windows-bt",
                "sys-windows-ws",
                "sys-windows-q",
                "sys-inplace-tr",
                "sys-esd",
                "sys-sysreset",
                "win-update-download",
                "user-inetcache",
                "user-webcache",
                "user-temporary-internet-files",
                "dev-npm-cache-roaming",
            },
        )
        self.assertEqual(
            self.index.match(r"C:\Windows.old")["recommendation"], "suggest"
        )

    def test_recommendation_tiers_and_labels_are_consistent(self):
        from disk_cleanup.model import (
            RECOMMENDATIONS,
            RECOMMENDATION_LABELS,
            RECOMMENDATION_SHORT,
        )

        self.assertEqual(
            RECOMMENDATIONS, ("suggest", "safe", "caution", "keep", "review")
        )
        for rec in RECOMMENDATIONS:
            self.assertIn(rec, RECOMMENDATION_LABELS)
            self.assertIn(rec, RECOMMENDATION_SHORT)
        self.assertEqual(RECOMMENDATION_LABELS["review"], "待定")
        self.assertEqual(RECOMMENDATION_LABELS["keep"], "建议保留")

    def test_language_annotation_and_validation(self):
        annotated = {
            rule["id"]: rule["language"]
            for rule in self.data["rules"]
            if rule.get("language")
        }
        self.assertGreaterEqual(len(annotated), 90)
        self.assertEqual(annotated["dev-node-modules"], "nodejs")
        self.assertEqual(annotated["dev-pip-cache"], "python")
        self.assertEqual(annotated["dev-cargo-registry-cache"], "rust")
        self.assertEqual(annotated["docker-vhdx"], "docker")
        # 系统类规则不标语言
        self.assertNotIn("sys-windows-old", annotated)

        bad = json.loads(json.dumps(self.data))
        bad["rules"][0]["language"] = "not-a-lang"
        self.assertTrue(
            any("language" in err for err in validate_rules(bad))
        )

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

    def test_runtime_node_modules_are_not_safe(self):
        # 运行时/插件自带的 node_modules 不是项目依赖，删了工具会起不来。
        runtime_paths = [
            r"C:\Users\alice\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules",
            r"C:\Users\alice\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\Lib\site-packages\artifact_tool_v2\bin\node_modules",
            r"C:\Users\alice\AppData\Local\OpenAI\Codex\runtimes\cua_node\bbc9141fe9f920ac\bin\node_modules",
            r"C:\Users\alice\AppData\Roaming\fnm\node-versions\v24.20.0\installation\node_modules",
            r"C:\Users\alice\.workbuddy\binaries\node\versions\22.22.2-6\node_modules",
            r"C:\Users\alice\.zcode\cli\plugins\cache\zcode-plugins-official\computer-use\0.5.13\node_modules",
        ]
        for path in runtime_paths:
            rule = self.index.match(path)
            self.assertIsNotNone(rule, path)
            self.assertEqual(rule["recommendation"], "keep", path)
        # 普通项目依赖仍然可清理
        self.assertEqual(
            self.index.match(r"D:\proj\node_modules")["recommendation"], "safe"
        )

    def test_runtime_roots_are_keep(self):
        cases = {
            r"C:\Users\alice\.cache\codex-runtimes": "rt-codex-runtimes",
            r"C:\Users\alice\AppData\Local\OpenAI\Codex\runtimes": "rt-openai-codex-runtimes",
            r"C:\Users\alice\AppData\Roaming\fnm\node-versions": "rt-fnm-node-versions",
            r"C:\Users\alice\.workbuddy\binaries": "rt-workbuddy-binaries",
            r"C:\Users\alice\.workbuddy\app": "rt-workbuddy-app",
            r"C:\Users\alice\.workbuddy\cli-connector-packages": "rt-workbuddy-connector",
            r"C:\Users\alice\.workbuddy\vendor": "rt-workbuddy-vendor",
            r"C:\Users\alice\.workbuddy\external-packages": "rt-workbuddy-external",
            r"C:\Users\alice\AppData\Local\Microsoft\TypeScript": "rt-typescript-sdk",
            r"C:\Users\alice\AppData\Roaming\nvm": "rt-nvm-windows",
            r"C:\Users\alice\.rustup\toolchains": "rt-rustup-toolchains",
            r"C:\Users\alice\.cargo\bin": "rt-cargo-bin",
            r"C:\Users\alice\AppData\Roaming\npm\node_modules": "rt-npm-global",
            r"C:\Program Files\nodejs\node_modules": "rt-nodejs-bundled",
        }
        for path, rule_id in cases.items():
            rule = self.index.match(path)
            self.assertIsNotNone(rule, path)
            self.assertEqual(rule["id"], rule_id, path)
            self.assertEqual(rule["recommendation"], "keep", path)

    def test_dev_tool_roots_are_containers(self):
        cases = {
            r"C:\Users\alice\.cargo": "dev-cargo-root",
            r"C:\Users\alice\.rustup": "dev-rustup-root",
            r"C:\Users\alice\AppData\Roaming\fnm": "dev-fnm-root",
            r"C:\Users\alice\AppData\Local\fnm": "dev-fnm-root-local",
        }
        for path, rule_id in cases.items():
            rule = self.index.match(path)
            self.assertIsNotNone(rule, path)
            self.assertEqual(rule["id"], rule_id, path)
            self.assertEqual(rule["recommendation"], "caution", path)
            self.assertEqual(rule["mode"], "container", path)
        # 既有缓存子规则不受容器规则影响
        self.assertEqual(
            self.index.match(r"C:\Users\alice\.rustup\downloads")["id"],
            "dev-rustup-downloads",
        )
        self.assertEqual(
            self.index.match(r"C:\Users\alice\.cargo\registry\src")["id"],
            "dev-cargo-registry-src",
        )

    def test_zcode_plugin_cache_is_caution_leaf(self):
        rule = self.index.match(r"C:\Users\alice\.zcode\cli\plugins\cache")
        self.assertIsNotNone(rule)
        self.assertEqual(rule["id"], "app-zcode-plugins-cache")
        self.assertEqual(rule["recommendation"], "caution")
        self.assertEqual(rule["mode"], "leaf")

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
