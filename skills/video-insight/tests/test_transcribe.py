import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from test_common import load_module


class TestHotwords(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("transcribe")

    def test_load_finance_preset(self):
        with TemporaryDirectory() as tmp:
            presets = Path(tmp) / "presets" / "hotwords"
            presets.mkdir(parents=True)
            (presets / "finance.txt").write_text(
                "筹码峰,K线,量价,阳线,阴线\n", encoding="utf-8"
            )
            with mock.patch.object(self.mod, "SKILL_DIR", Path(tmp)):
                words = self.mod.load_preset("finance")
        self.assertEqual(words, ["筹码峰", "K线", "量价", "阳线", "阴线"])

    def test_unknown_preset_raises(self):
        with self.assertRaises(FileNotFoundError):
            self.mod.load_preset("nope")

    def test_merge_dedupes(self):
        self.assertEqual(
            self.mod.merge_hotwords(["K线", "量价"], "量价, 诱多 ,"),
            "K线,量价,诱多",
        )


if __name__ == "__main__":
    unittest.main()
