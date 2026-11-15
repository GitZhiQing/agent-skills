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
                "app-pixpin-upgrade",
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

    def test_vendor_containers_are_caution(self):
        cases = {
            r"C:\Users\alice\AppData\LocalLow\Unity": "game-unity-locallow",
            r"C:\Users\alice\AppData\Roaming\Tencent": "app-tencent",
            r"C:\Users\alice\AppData\Local\JianyingPro": "app-jianying",
            r"C:\Users\alice\AppData\Roaming\LarkShell": "app-larkshell",
            r"C:\Users\alice\AppData\Roaming\kingsoft": "app-kingsoft",
            r"C:\Users\alice\AppData\Local\PixPin": "app-pixpin",
            r"C:\Users\alice\.zcode": "app-zcode-root",
            r"C:\Users\alice\.workbuddy": "app-workbuddy-root",
            r"C:\Users\alice\.codex": "app-codex-cli-root",
            r"C:\Users\alice\AppData\Roaming\Code": "app-vscode-root",
            r"C:\Users\alice\AppData\Local\BraveSoftware": "app-brave-root",
            r"C:\Users\alice\.cache": "dev-cache-root",
            r"C:\Users\alice\AppData\Local\Packages": "app-packages-root",
            r"C:\Users\alice\AppData\Local\Google": "app-google-root",
            r"C:\Users\alice\AppData\Local\Microsoft": "app-microsoft-local",
        }
        for path, rule_id in cases.items():
            rule = self.index.match(path)
            self.assertIsNotNone(rule, path)
            self.assertEqual(rule["id"], rule_id, path)
            self.assertEqual(rule["recommendation"], "caution", path)
            self.assertEqual(rule["mode"], "container", path)

    def test_pixpin_user_data_is_keep(self):
        for sub in ("History", "Data", "Config"):
            rule = self.index.match(rf"C:\Users\alice\AppData\Local\PixPin\{sub}")
            self.assertIsNotNone(rule, sub)
            self.assertEqual(rule["recommendation"], "keep", sub)
        self.assertEqual(
            self.index.match(r"C:\Users\alice\AppData\Local\PixPin\UpgradeFiles")[
                "recommendation"
            ],
            "suggest",
        )
        self.assertEqual(
            self.index.match(r"C:\Users\alice\AppData\Local\PixPin\Crashpad")[
                "recommendation"
            ],
            "safe",
        )

    def test_wps_rules(self):
        cases = {
            r"C:\Users\alice\AppData\Roaming\kingsoft\wps\addons\pool": ("caution", "app-wps-addons-pool"),
            r"C:\Users\alice\AppData\Roaming\kingsoft\office6\backup": ("keep", "app-wps-office6-backup"),
            r"C:\Users\alice\AppData\Roaming\kingsoft\kaccountsdk": ("keep", "app-wps-kaccountsdk"),
            r"C:\Users\alice\AppData\Roaming\kingsoft\office6\cache": ("safe", "app-wps-office6-cache"),
            r"C:\Users\alice\AppData\Roaming\kingsoft\WPS Cloud Files": ("caution", "app-wps-cloud-files"),
        }
        for path, (rec, rule_id) in cases.items():
            rule = self.index.match(path)
            self.assertIsNotNone(rule, path)
            self.assertEqual(rule["id"], rule_id, path)
            self.assertEqual(rule["recommendation"], rec, path)

    def test_lark_cache_globs(self):
        base = r"C:\Users\alice\AppData\Roaming\LarkShell\aha\users\123\profile_explorer"
        for sub in ("Cache", "Code Cache", "GPUCache", r"Service Worker\CacheStorage"):
            rule = self.index.match(base + "\\" + sub)
            self.assertIsNotNone(rule, sub)
            self.assertEqual(rule["recommendation"], "safe", sub)

    def test_jianying_rules(self):
        base = r"C:\Users\alice\AppData\Local\JianyingPro"
        self.assertEqual(self.index.match(base + r"\User Data\Cache")["recommendation"], "safe")
        self.assertEqual(self.index.match(base + r"\User Data\CEF\ShaderCache")["recommendation"], "safe")
        self.assertEqual(self.index.match(base + r"\User Data\Projects")["recommendation"], "keep")
        self.assertEqual(self.index.match(base + r"\Apps")["recommendation"], "keep")
        self.assertEqual(self.index.match(base + r"\User Data\Config")["recommendation"], "keep")

    def test_tencent_rules(self):
        base = r"C:\Users\alice\AppData\Roaming\Tencent"
        cases = {
            r"\QQ\STemp": "safe",
            r"\QQNT\STemp": "safe",
            r"\WeMail\cache": "safe",
            r"\xwechat\log": "safe",
            r"\WeMail\local_draft": "keep",
            r"\WeMail\attachments": "caution",
            r"\WeMeet\Users": "caution",
        }
        for sub, rec in cases.items():
            rule = self.index.match(base + sub)
            self.assertIsNotNone(rule, sub)
            self.assertEqual(rule["recommendation"], rec, sub)

    def test_game_cache_rules(self):
        self.assertEqual(
            self.index.match(r"C:\Users\alice\AppData\LocalLow\Unity\com_proximabeta_NIKKE")[
                "recommendation"
            ],
            "safe",
        )
        self.assertEqual(
            self.index.match(r"C:\Users\alice\AppData\LocalLow\com_proximabeta\NIKKE\saus")[
                "recommendation"
            ],
            "safe",
        )

    def test_updater_regex_is_anchored(self):
        for name in ("cherrystudio-updater", "@zcodedesktop-updater", "apifox-updater"):
            rule = self.index.match(rf"C:\Users\alice\AppData\Local\{name}")
            self.assertIsNotNone(rule, name)
            self.assertEqual(rule["id"], "app-electron-updater", name)
            self.assertEqual(rule["recommendation"], "safe", name)
        # 项目里名为 foo-updater 的源码目录不得命中
        self.assertIsNone(self.index.match(r"D:\proj\foo-updater"))
        self.assertIsNone(self.index.match(r"C:\Users\alice\AppData\Local\sub\foo-updater"))
        self.assertEqual(
            self.index.match(r"C:\Users\alice\AppData\Local\SquirrelTemp")["id"],
            "app-squirreltemp",
        )

    def test_agent_state_rules(self):
        cases = {
            r"C:\Users\alice\.zcode\skills": "keep",
            r"C:\Users\alice\.zcode\v2\credentials": "keep",
            r"C:\Users\alice\.zcode\cli\log": "safe",
            r"C:\Users\alice\.workbuddy\sessions": "caution",
            r"C:\Users\alice\.workbuddy\cache": "safe",
            r"C:\Users\alice\.workbuddy\skills": "keep",
            r"C:\Users\alice\.codex\sessions": "caution",
            r"C:\Users\alice\.codex\log": "safe",
        }
        for path, rec in cases.items():
            rule = self.index.match(path)
            self.assertIsNotNone(rule, path)
            self.assertEqual(rule["recommendation"], rec, path)

    def test_vscode_family_completion(self):
        cases = {
            r"C:\Users\alice\AppData\Roaming\Code\CachedExtensionVSIXs": "safe",
            r"C:\Users\alice\AppData\Roaming\Code\User\History": "caution",
            r"C:\Users\alice\AppData\Roaming\Code\User\snippets": "keep",
            r"C:\Users\alice\AppData\Roaming\Code\Backups": "caution",
            r"C:\Users\alice\AppData\Roaming\Trae CN\CachedData": "safe",
            r"C:\Users\alice\AppData\Roaming\Trae CN\Backups": "caution",
            r"C:\Users\alice\AppData\Roaming\CodeBuddy CN\Cache": "safe",
            r"C:\Users\alice\AppData\Local\CodeBuddyExtension\Logs": "safe",
            r"C:\Users\alice\AppData\Roaming\Qoder\CachedData": "safe",
        }
        for path, rec in cases.items():
            rule = self.index.match(path)
            self.assertIsNotNone(rule, path)
            self.assertEqual(rule["recommendation"], rec, path)

    def test_brave_chrome_completion(self):
        brave = r"C:\Users\alice\AppData\Local\BraveSoftware\Brave-Browser\User Data"
        self.assertEqual(self.index.match(brave + r"\Default\Code Cache")["id"], "brave-code-cache")
        self.assertEqual(self.index.match(brave + r"\Default\DawnWebGPUCache")["recommendation"], "safe")
        self.assertEqual(self.index.match(brave + r"\Crashpad")["recommendation"], "safe")
        chrome = r"C:\Users\alice\AppData\Local\Google\Chrome\User Data"
        self.assertEqual(self.index.match(chrome + r"\component_crx_cache")["recommendation"], "safe")
        self.assertEqual(self.index.match(chrome + r"\Default\DawnGraphiteCache")["recommendation"], "safe")
        self.assertEqual(self.index.match(chrome + r"\Crashpad")["recommendation"], "safe")

    def test_credential_and_userdata_keeps(self):
        paths = [
            r"C:\Users\alice\AppData\Local\Microsoft\Credentials",
            r"C:\Users\alice\AppData\Local\Microsoft\Vault",
            r"C:\Users\alice\AppData\Local\Microsoft\TokenBroker",
            r"C:\Users\alice\AppData\Roaming\Telegram Desktop\tdata",
            r"C:\Users\alice\AppData\Local\1Password",
            r"C:\Users\alice\AppData\Roaming\Bitwarden",
            r"C:\Users\alice\AppData\Roaming\Composer",
            r"C:\Users\alice\AppData\Local\GOG.com\Galaxy\storage",
            r"C:\Users\alice\AppData\Roaming\Zed",
            r"C:\Users\alice\AppData\Roaming\Godot",
            r"D:\vaults\notes\.obsidian",
        ]
        for path in paths:
            rule = self.index.match(path)
            self.assertIsNotNone(rule, path)
            self.assertEqual(rule["recommendation"], "keep", path)

    def test_mainstream_dev_rules(self):
        cases = {
            r"C:\Users\alice\AppData\Local\deno\deps": "safe",
            r"C:\Users\alice\AppData\Local\deno\location_data": "caution",
            r"C:\Users\alice\AppData\Local\Volta": "keep",
            r"C:\Users\alice\AppData\Roaming\uv\python": "keep",
            r"C:\Users\alice\AppData\Local\electron": "safe",
            r"C:\Users\alice\AppData\Local\Zed\logs": "safe",
            r"C:\Users\alice\AppData\Local\Composer\cache": "safe",
            r"C:\Users\alice\AppData\Local\Pandoc": "keep",
            r"C:\Users\alice\AppData\Local\Temp\Godot": "safe",
        }
        for path, rec in cases.items():
            rule = self.index.match(path)
            self.assertIsNotNone(rule, path)
            self.assertEqual(rule["recommendation"], rec, path)

    def test_mainstream_app_rules(self):
        cases = {
            r"C:\Users\alice\Documents\xwechat_files": ("caution", "app-wechat-files"),
            r"C:\Users\alice\Documents\xwechat_files\wxid_123\db_storage": ("keep", "wechat4-db"),
            r"C:\Users\alice\Documents\xwechat_files\wxid_123\cache": ("safe", "wechat4-cache"),
            r"C:\Users\alice\Documents\WeChat Files\wxid_123\FileStorage": ("caution", "wechat3-filestorage"),
            r"C:\Users\alice\Documents\Tencent Files": ("caution", "app-qq-files"),
            r"C:\Users\alice\AppData\Roaming\DingTalk\Cache": ("safe", "dingtalk-cache"),
            r"C:\Users\alice\AppData\Roaming\Figma\DesktopProfile\Cache": ("safe", "figma-cache"),
            r"C:\Users\alice\AppData\Roaming\CherryStudio\Cache": ("safe", "cherrystudio-cache"),
            r"C:\Users\alice\AppData\Roaming\Adobe\Common\Media Cache Files": ("safe", "adobe-media-cache-files"),
            r"C:\CacheClip": ("safe", "davinci-cacheclip"),
            r"C:\Users\alice\AppData\Roaming\HoYoPlay\Cache": ("safe", "hoyoplay-cache"),
            r"C:\ProgramData\GOG.com\Galaxy\webcache": ("safe", "gog-webcache"),
            r"C:\Users\alice\AppData\Local\Electronic Arts\EA Desktop\cache": ("safe", "ea-cache"),
            r"C:\Users\alice\AppData\Local\Ubisoft Game Launcher\cache": ("safe", "ubisoft-cache"),
        }
        for path, (rec, rule_id) in cases.items():
            rule = self.index.match(path)
            self.assertIsNotNone(rule, path)
            self.assertEqual(rule["id"], rule_id, path)
            self.assertEqual(rule["recommendation"], rec, path)

    def test_system_and_driver_rules(self):
        rule = self.index.match(r"C:\$WinREAgent")
        self.assertEqual(rule["id"], "win-winreagent")
        self.assertEqual(rule["recommendation"], "caution")
        self.assertTrue(rule.get("requires_admin"))
        rule = self.index.match(
            r"C:\Windows\ServiceProfiles\NetworkService\AppData\Local\Microsoft\Windows\DeliveryOptimization\Cache"
        )
        self.assertEqual(rule["id"], "win-do-cache")
        self.assertEqual(rule["recommendation"], "safe")
        self.assertTrue(rule.get("requires_admin"))
        self.assertEqual(
            self.index.match(r"C:\Users\alice\AppData\LocalLow\NVIDIA\DXCache")[
                "recommendation"
            ],
            "safe",
        )

    def test_longtail_dev_and_vendor_rules(self):
        cases = {
            r"C:\Users\alice\.bun\bin": "keep",
            r"C:\Users\alice\.bun\install": "safe",
            r"C:\Users\alice\AppData\Roaming\Python": "keep",
            r"C:\Users\alice\AppData\Local\node-gyp": "safe",
            r"C:\Users\alice\AppData\Local\pnpm-cache": "safe",
            r"C:\Users\alice\npm-cache": "safe",
            r"C:\Users\alice\AppData\Local\ms-playwright-mcp": "safe",
            r"C:\Users\alice\AppData\Roaming\Mozilla": "caution",
            r"C:\Users\alice\AppData\Local\Epic Games": "caution",
            r"C:\Users\alice\AppData\Roaming\baidunetdisk": "caution",
            r"C:\Users\alice\AppData\LocalLow\Hypergryph": "caution",
        }
        for path, rec in cases.items():
            rule = self.index.match(path)
            self.assertIsNotNone(rule, path)
            self.assertEqual(rule["recommendation"], rec, path)

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
