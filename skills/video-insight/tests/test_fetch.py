import unittest
from pathlib import Path
from unittest import mock

from test_common import load_module


class TestClassify(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("fetch")

    def test_bilibili_variants(self):
        for url in (
            "https://www.bilibili.com/video/BV1DJYe6AEgP",
            "https://bilibili.com/video/BV1DJYe6AEgP",
            "https://m.bilibili.com/video/BV1DJYe6AEgP",
            "https://b23.tv/abc123",
        ):
            platform, host = self.mod.classify(url)
            self.assertEqual(platform, "bilibili", url)

    def test_dropped_platforms(self):
        cases = {
            "https://v.douyin.com/rVWFVso/": "douyin",
            "https://www.douyin.com/video/7168743658076900608": "douyin",
            "https://www.xiaohongshu.com/explore/xyz": "xiaohongshu",
            "https://xhslink.com/abc": "xiaohongshu",
            "https://www.kuaishou.com/short-video/xyz": "kuaishou",
        }
        for url, expected in cases.items():
            platform, _ = self.mod.classify(url)
            self.assertEqual(platform, expected, url)

    def test_unknown(self):
        platform, host = self.mod.classify("https://example.com/video")
        self.assertEqual(platform, "unknown")
        self.assertEqual(host, "example.com")


class TestSupportPolicy(unittest.TestCase):
    """Every dropped platform must carry a concrete reason + re-entry rule."""

    def setUp(self):
        self.mod = load_module("fetch")

    def test_dropped_reasons_are_substantive(self):
        for platform, reason in self.mod.DROPPED.items():
            self.assertGreater(len(reason), 20, platform)
            # every reason must cite its evidence class: extractor issues,
            # absence of a link-parsing path, or lack of verification
            self.assertRegex(reason, r"yt-dlp|无链接|未验证", platform)

    def test_supported_and_dropped_are_disjoint(self):
        self.assertFalse(set(self.mod.SUPPORTED_HOSTS) & set(self.mod.DROPPED_HOSTS))


class TestBuildCmd(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("fetch")

    def test_command_shape(self):
        with mock.patch.object(self.mod, "yt_dlp_cmd", return_value=["yt-dlp"]):
            cmd = self.mod.build_cmd(
                "https://www.bilibili.com/video/BV1x",
                target=Path("out/video.mp4"),
                ytdl_format="bv*+ba/b",
                cookies_from_browser=None,
            )
        self.assertEqual(cmd[0], "yt-dlp")
        self.assertIn("--no-playlist", cmd)
        self.assertIn("--merge-output-format", cmd)
        self.assertEqual(cmd[-1], "https://www.bilibili.com/video/BV1x")

    def test_cookies_passthrough(self):
        with mock.patch.object(self.mod, "yt_dlp_cmd", return_value=["yt-dlp"]):
            cmd = self.mod.build_cmd(
                "https://www.bilibili.com/video/BV1x",
                target=Path("out/video.mp4"),
                ytdl_format="bv*+ba/b",
                cookies_from_browser="chrome",
            )
        self.assertIn("chrome", cmd)


if __name__ == "__main__":
    unittest.main()
