import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from test_common import load_module


def doc(screens):
    return {
        "mode": "uniform",
        "time_precision": "approx",
        "screens": screens,
    }


def row(i, t0, t1, text, **extra):
    return {"i": i, "t_start": t0, "t_end": t1, "grab_at": (t0 + t1) / 2,
            "basis": "sample", "text": text, "readability": "清晰",
            "mean_confidence": None, "evidence_frames": [],
            "merged_from": [i], **extra}


class TestRenderSrt(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("screen_srt")

    def test_numbering_and_timestamps(self):
        srt, cues, skipped = self.mod.render_srt(doc([
            row(1, 0.0, 2.0, "第一屏"),
            row(2, 2.0, 4.35, "第二屏"),
        ]))
        self.assertEqual(cues, 2)
        self.assertEqual(skipped, 0)
        self.assertIn("1\n00:00:00,000 --> 00:00:02,000\n第一屏", srt)
        self.assertIn("2\n00:00:02,000 --> 00:00:04,350\n第二屏", srt)

    def test_cjk_quotes_survive_verbatim(self):
        text = "「诱多」 ≠ “诱空”：别猜！"
        srt, _, _ = self.mod.render_srt(doc([row(1, 0.0, 1.0, text)]))
        self.assertIn(text, srt)

    def test_empty_text_rows_skipped_numbers_stay_sequential(self):
        srt, cues, skipped = self.mod.render_srt(doc([
            row(1, 0.0, 1.0, "有字"),
            row(2, 1.0, 2.0, "   "),
            row(3, 2.0, 3.0, ""),
        ]))
        self.assertEqual((cues, skipped), (1, 2))
        self.assertNotIn("2\n", srt)

    def test_bad_schema_raises(self):
        with self.assertRaises(self.mod.SchemaError):
            self.mod.render_srt({"mode": "event"})
        with self.assertRaises(self.mod.SchemaError):
            self.mod.render_srt(doc([{"i": 1, "text": "没有时间戳"}]))


class TestCli(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("screen_srt")
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)

    def test_renders_next_to_input_and_records_manifest(self):
        path = self.out / "transcript.screen.json"
        path.write_text(json.dumps(doc([row(1, 0.0, 2.0, "第一屏")]),
                                   ensure_ascii=False), encoding="utf-8")
        code = self.mod.main([str(path)])
        self.assertEqual(code, 0)
        srt = (self.out / "transcript.screen.srt").read_text(encoding="utf-8")
        self.assertIn("第一屏", srt)
        manifest = json.loads((self.out / "manifest.json")
                              .read_text(encoding="utf-8"))
        self.assertEqual(manifest["scripts"]["screen_srt"]["status"], "ok")

    def test_bad_schema_exit_2(self):
        path = self.out / "transcript.screen.json"
        path.write_text(json.dumps({"mode": "event"}), encoding="utf-8")
        code = self.mod.main([str(path), "--output-dir", str(self.out)])
        self.assertEqual(code, 2)

    def test_missing_input_exit_1(self):
        code = self.mod.main([str(self.out / "nope.json")])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
