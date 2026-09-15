import subprocess
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
                    mock.patch.object(self.mod, "resolve_asr",
                                      side_effect=AssertionError("no ASR needed")):
                result = self.mod.transcribe(video, Path(tmp), "none", None, None)
        self.assertTrue(result["no_speech"])
        self.assertEqual(result["reason"], "no_audio_track")

    def test_asr_empty_returns_no_speech(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp)
            video = out / "v.mp4"
            video.write_bytes(b"x")
            (out / "tmp" / "asr").mkdir(parents=True)  # ASR ran, produced nothing

            def fake_run(cmd, **kwargs):
                argv = [str(c) for c in cmd]
                if argv[0] == "ffprobe":
                    return self._proc(0, "audio\n")
                return self._proc(0, "")

            with mock.patch.object(self.mod, "run", side_effect=fake_run), \
                    mock.patch.object(self.mod, "resolve_asr",
                                      return_value={"ok": True, "asr_script": "fake.py"}):
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
                return self._proc(1, "")

            with mock.patch.object(self.mod, "run", side_effect=fake_run), \
                    mock.patch.object(self.mod, "resolve_asr",
                                      return_value={"ok": True, "asr_script": "fake.py"}):
                with self.assertRaises(RuntimeError):
                    self.mod.transcribe(video, out, "none", None, None)

    def test_suspect_no_speech_flag_on_tiny_output(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp)
            video = out / "v.mp4"
            video.write_bytes(b"x")
            asr_out = out / "tmp" / "asr"
            asr_out.mkdir(parents=True)
            (asr_out / "text.txt").write_text("嗯", encoding="utf-8")

            def fake_run(cmd, **kwargs):
                argv = [str(c) for c in cmd]
                if argv[0] == "ffprobe":
                    return self._proc(0, "audio\n")
                return self._proc(0, "")

            with mock.patch.object(self.mod, "run", side_effect=fake_run), \
                    mock.patch.object(self.mod, "resolve_asr",
                                      return_value={"ok": True, "asr_script": "fake.py"}):
                result = self.mod.transcribe(video, out, "none", None, None)
        self.assertFalse(result.get("no_speech"))
        self.assertTrue(result["info"]["suspect_no_speech"])


if __name__ == "__main__":
    unittest.main()
