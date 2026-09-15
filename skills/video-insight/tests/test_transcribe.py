import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from test_common import load_module

CFG = {
    "key": "k",
    "resource_id": "volc.seedasr.auc",
    "api_base": "https://openspeech.bytedance.com",
}


def _asr_result(txt="", srt="", raw=None):
    return {"srt": srt, "txt": txt, "raw": raw or {}, "request_id": "rid-1"}


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


class TestNoSpeech(unittest.TestCase):
    """Empty-ASR / no-audio-track are branch signals, not fatal errors."""

    def setUp(self):
        self.mod = load_module("transcribe")

    @staticmethod
    def _proc(returncode=0, stdout=""):
        return subprocess.CompletedProcess([], returncode, stdout, "")

    def test_no_audio_track_short_circuits(self):
        with TemporaryDirectory() as tmp:
            video = Path(tmp) / "v.mp4"
            video.write_bytes(b"x")

            def fake_run(cmd, **kwargs):
                return self._proc(0, "")  # ffprobe lists no audio stream

            with mock.patch.object(self.mod, "run", side_effect=fake_run), \
                    mock.patch.object(
                        self.mod.asr_volc, "api_config",
                        side_effect=AssertionError("no ASR needed")):
                result = self.mod.transcribe(video, Path(tmp), "none", None, None)
        self.assertTrue(result["no_speech"])
        self.assertEqual(result["reason"], "no_audio_track")

    def test_asr_empty_returns_no_speech(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp)
            video = out / "v.mp4"
            video.write_bytes(b"x")

            def fake_run(cmd, **kwargs):
                argv = [str(c) for c in cmd]
                if argv[0] == "ffprobe":
                    return self._proc(0, "audio\n")
                return self._proc(0, "")

            with mock.patch.object(self.mod, "run", side_effect=fake_run), \
                    mock.patch.object(self.mod.asr_volc, "api_config",
                                      return_value=CFG), \
                    mock.patch.object(self.mod.asr_volc, "transcribe_audio",
                                      return_value=_asr_result()):
                result = self.mod.transcribe(video, out, "none", None, None)
        self.assertTrue(result["no_speech"])
        self.assertEqual(result["reason"], "asr_empty")
        self.assertFalse((out / "tmp").exists())  # cleaned up

    def test_asr_failure_still_raises(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp)
            video = out / "v.mp4"
            video.write_bytes(b"x")

            def fake_run(cmd, **kwargs):
                argv = [str(c) for c in cmd]
                if argv[0] == "ffprobe":
                    return self._proc(0, "audio\n")
                return self._proc(0, "")

            with mock.patch.object(self.mod, "run", side_effect=fake_run), \
                    mock.patch.object(self.mod.asr_volc, "api_config",
                                      return_value=CFG), \
                    mock.patch.object(self.mod.asr_volc, "transcribe_audio",
                                      side_effect=RuntimeError("HTTP 401")):
                with self.assertRaises(RuntimeError):
                    self.mod.transcribe(video, out, "none", None, None)

    def test_suspect_no_speech_flag_on_tiny_output(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp)
            video = out / "v.mp4"
            video.write_bytes(b"x")

            def fake_run(cmd, **kwargs):
                argv = [str(c) for c in cmd]
                if argv[0] == "ffprobe":
                    return self._proc(0, "audio\n")
                return self._proc(0, "")

            with mock.patch.object(self.mod, "run", side_effect=fake_run), \
                    mock.patch.object(self.mod.asr_volc, "api_config",
                                      return_value=CFG), \
                    mock.patch.object(
                        self.mod.asr_volc, "transcribe_audio",
                        return_value=_asr_result(txt="嗯")):
                result = self.mod.transcribe(video, out, "none", None, None)
        self.assertFalse(result.get("no_speech"))
        self.assertTrue(result["info"]["suspect_no_speech"])


class TestSuccess(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("transcribe")

    @staticmethod
    def _proc(returncode=0, stdout=""):
        return subprocess.CompletedProcess([], returncode, stdout, "")

    def _fake_run(self):
        def fake_run(cmd, **kwargs):
            argv = [str(c) for c in cmd]
            if argv[0] == "ffprobe":
                return self._proc(0, "audio\n")
            return self._proc(0, "")
        return fake_run

    def test_writes_transcripts_and_backend_info(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp)
            video = out / "v.mp4"
            video.write_bytes(b"x")
            raw = {"result": {
                "text": "这是口播内容",
                "utterances": [
                    {"text": "这是口播内容", "start_time": 0, "end_time": 2000},
                ],
            }}
            srt = "1\n00:00:00,000 --> 00:00:02,000\n这是口播内容"
            with mock.patch.object(self.mod, "run",
                                   side_effect=self._fake_run()), \
                    mock.patch.object(self.mod.asr_volc, "api_config",
                                      return_value=CFG), \
                    mock.patch.object(self.mod.asr_volc, "transcribe_audio",
                                      return_value=_asr_result(
                                          txt="这是口播内容", srt=srt, raw=raw)):
                result = self.mod.transcribe(video, out, "none", None, None)
            names = {p.name for p in result["produced"]}
            self.assertEqual(names, {"transcript.srt", "transcript.txt",
                                     "transcript.json"})
            for p in result["produced"]:
                self.assertGreater((out / p.name).stat().st_size, 0)
            self.assertFalse((out / "tmp").exists())  # temp audio cleaned up
            info = result["info"]
            self.assertEqual(info["asr_backend"], "volc_seedasr")
            self.assertEqual(info["model"], "volc.seedasr.auc")
            self.assertEqual(info["api_base"], CFG["api_base"])
            self.assertEqual(info["request_id"], "rid-1")
            self.assertFalse(info["suspect_no_speech"])
            self.assertIn("这是口播内容",
                          (out / "transcript.txt").read_text(encoding="utf-8"))

    def test_no_utterances_skips_srt_keeps_txt_json(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp)
            video = out / "v.mp4"
            video.write_bytes(b"x")
            with mock.patch.object(self.mod, "run",
                                   side_effect=self._fake_run()), \
                    mock.patch.object(self.mod.asr_volc, "api_config",
                                      return_value=CFG), \
                    mock.patch.object(self.mod.asr_volc, "transcribe_audio",
                                      return_value=_asr_result(txt="短文本")):
                result = self.mod.transcribe(video, out, "none", None, None)
            names = {p.name for p in result["produced"]}
            self.assertEqual(names, {"transcript.txt", "transcript.json"})
            self.assertTrue(result["info"]["suspect_no_speech"])


if __name__ == "__main__":
    unittest.main()
