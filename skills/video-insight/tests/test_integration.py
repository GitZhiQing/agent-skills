"""Integration test: run the whole ffmpeg-backed pipeline on synthetic videos.

Skipped automatically when ffmpeg (with libx264) is unavailable.
"""

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from test_common import load_module

ROOT_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

FONT_CANDIDATES = (
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/msyh.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)


def _can_encode_h264_aac() -> bool:
    if not FFMPEG:
        return False
    try:
        proc = subprocess.run(
            [FFMPEG, "-hide_banner", "-encoders"], capture_output=True, timeout=30
        )
        text = proc.stdout.decode("utf-8", "replace")
    except Exception:
        return False
    return "libx264" in text and " aac" in text


def _find_font() -> str | None:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None


def _has_drawtext() -> bool:
    if not FFMPEG:
        return False
    try:
        proc = subprocess.run(
            [FFMPEG, "-hide_banner", "-filters"], capture_output=True, timeout=30
        )
        return " drawtext " in proc.stdout.decode("utf-8", "replace")
    except Exception:
        return False


def _text_card_filter(font: str) -> str:
    cards = [
        ("SCREEN ONE", "white", 0, 2),
        ("SCREEN TWO", "yellow", 2, 4),
        ("SCREEN THREE", "cyan", 4, 6),
    ]
    parts = [
        f"drawtext=text='{text}':fontsize=56:fontcolor={color}"
        f":x=(w-text_w)/2:y=(h-text_h)/2:fontfile='{font}'"
        f":enable='between(t,{lo},{hi})'"
        for text, color, lo, hi in cards
    ]
    return ",".join(parts)


@unittest.skipUnless(
    FFMPEG and FFPROBE and _can_encode_h264_aac(), "ffmpeg with libx264/aac required"
)
class TestPipelineOnSyntheticVideo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.video = cls.root / "synth.mp4"
        subprocess.run(
            [
                FFMPEG, "-loglevel", "error",
                "-f", "lavfi", "-i", "testsrc2=duration=3:size=320x240:rate=30",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-y", str(cls.video),
            ],
            capture_output=True,
            timeout=120,
        )
        assert cls.video.exists() and cls.video.stat().st_size > 0, "synthetic video encoding failed"
        cls.out = cls.root / "out"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_script(self, name, *argv):
        result = subprocess.run(
            [sys.executable, str(ROOT_SCRIPTS / f"{name}.py"), *argv, "--output-dir", str(self.out)],
            capture_output=True,
            timeout=300,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace")[-2000:])
        return json.loads(result.stdout.decode("utf-8", "replace"))

    def test_01_probe(self):
        summary = self.run_script("probe", str(self.video))
        self.assertEqual(summary["video"]["width"], 320)
        self.assertEqual(summary["video"]["height"], 240)
        self.assertAlmostEqual(summary["duration_s"], 3.0, delta=0.1)

    def test_02_extract_frames(self):
        summary = self.run_script("extract_frames", str(self.video))
        self.assertEqual(summary["overview_images"], 1)
        self.assertEqual(summary["overview_expected"], 1)
        manifest = json.loads((self.out / "data" / "frames_overview.json").read_text(encoding="utf-8"))
        cells = manifest["images"][0]["cells"]
        stamped = [c for c in cells if c["t_exact"] is not None]
        self.assertEqual(len(stamped), 3)  # 3 seconds of testsrc2
        self.assertEqual([c["t_exact"] for c in stamped], [0.0, 1.0, 2.0])
        self.assertTrue((self.out / "evidence" / "subtitle-strip" / "strip_01.jpg").exists())

    def test_03_detect_changes(self):
        summary = self.run_script("detect_changes", str(self.video))
        # testsrc2 changes every frame -> at least one big merged event
        self.assertGreaterEqual(summary["n_events"], 1)

    def test_04_grab_frames(self):
        summary = self.run_script("grab_frames", str(self.video), "--at", "1.0", "--label", "synth")
        self.assertEqual(summary["grabbed"], 1)
        self.assertTrue((self.out / "evidence" / "keyframes" / "synth_1s.jpg").exists())

    def test_05_grab_crop(self):
        self.run_script(
            "grab_frames", str(self.video),
            "--at", "1.0", "--crop", "160x120+0+0", "--zoom", "4",
            "--label", "synth_crop",
        )
        crop = self.out / "evidence" / "crops" / "synth_crop_1s_160x120_x4.png"
        self.assertTrue(crop.exists() and crop.stat().st_size > 0)

    def test_06_palette(self):
        summary = self.run_script(
            "palette", str(self.video), "--at", "1.0", "--crop", "160x120+0+0"
        )
        self.assertTrue(summary["dominant_any"])
        # saturated clusters partition the region: their shares sum to <= 1
        self.assertLessEqual(sum(e["share"] for e in summary["saturated"]), 1.0)
        for entry in summary["dominant_any"] + summary["saturated"]:
            self.assertLessEqual(entry["share"], 1.0)

    def test_07_audio_probe(self):
        summary = self.run_script("audio_probe", str(self.video))
        self.assertIsNotNone(summary["loudness"]["lufs"])
        self.assertEqual(summary["pauses"], 0)  # continuous sine, no silence
        self.assertTrue((self.out / "evidence" / "audio" / "spectrogram_full.png").exists())

    def test_08_manifest_all_ok(self):
        manifest = json.loads((self.out / "manifest.json").read_text(encoding="utf-8"))
        statuses = {name: rec["status"] for name, rec in manifest["scripts"].items()}
        for name, status in statuses.items():
            self.assertEqual(status, "ok", f"{name} recorded status {status}")


@unittest.skipUnless(
    FFMPEG and FFPROBE and _can_encode_h264_aac() and _has_drawtext() and _find_font(),
    "ffmpeg with libx264 + drawtext + a font required",
)
class TestNoSpeechTextCards(unittest.TestCase):
    """A BGM-less text-card video: the no-speech branch of the pipeline."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.video = cls.root / "textcards.mp4"
        subprocess.run(
            [
                FFMPEG, "-loglevel", "error",
                "-f", "lavfi", "-i", "color=black:size=640x360:rate=30:duration=6",
                "-vf", _text_card_filter(_find_font().replace(":", r"\:")),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-y", str(cls.video),
            ],
            capture_output=True,
            timeout=120,
        )
        assert cls.video.exists() and cls.video.stat().st_size > 0, "text-card encoding failed"
        cls.out = cls.root / "out"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_script(self, name, *argv):
        result = subprocess.run(
            [sys.executable, str(ROOT_SCRIPTS / f"{name}.py"), *argv, "--output-dir", str(self.out)],
            capture_output=True,
            timeout=300,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace")[-2000:])
        return json.loads(result.stdout.decode("utf-8", "replace"))

    def test_01_probe_reports_no_audio(self):
        summary = self.run_script("probe", str(self.video))
        self.assertEqual(summary["audio"], {})

    def test_02_transcribe_no_speech_not_fatal(self):
        summary = self.run_script("transcribe", str(self.video))
        self.assertTrue(summary["no_speech"])
        self.assertEqual(summary["reason"], "no_audio_track")
        self.assertEqual(summary["status"], "no_speech")

    def test_03_detect_changes_finds_card_switches(self):
        summary = self.run_script("detect_changes", str(self.video))
        self.assertEqual(summary["n_events"], 2)
        starts = sorted(
            float(chunk.split("(")[0]) for chunk in summary["events"]
        )
        self.assertAlmostEqual(starts[0], 2.0, delta=0.2)
        self.assertAlmostEqual(starts[1], 4.0, delta=0.2)

    def test_04_screen_segments_three_screens(self):
        self.run_script("detect_changes", str(self.video))
        summary = self.run_script(
            "screen_segments", str(self.out / "data" / "changes.json")
        )
        self.assertEqual(summary["n_screens"], 3)
        self.assertEqual(summary["mode"], "event")
        segments = json.loads(
            (self.out / "data" / "screen_segments.json").read_text(encoding="utf-8")
        )["segments"]
        self.assertEqual(segments[0]["t_start"], 0.0)
        self.assertAlmostEqual(segments[0]["t_end"], 2.0, delta=0.2)
        self.assertAlmostEqual(segments[1]["t_start"], 2.0, delta=0.2)
        self.assertAlmostEqual(segments[2]["t_end"], 6.0, delta=0.1)
        for seg in segments:
            self.assertTrue(seg["t_start"] <= seg["grab_at"] <= seg["t_end"])

    def test_05_grab_frames_per_segment(self):
        summary = self.run_script(
            "grab_frames", str(self.video), "--at", "1.0,3.0,5.0", "--label", "card"
        )
        self.assertEqual(summary["grabbed"], 3)
        for t in (1, 3, 5):
            self.assertTrue(
                (self.out / "evidence" / "keyframes" / f"card_{t}s.jpg").exists()
            )

    def test_06_manifest_mixed_status(self):
        manifest = json.loads((self.out / "manifest.json").read_text(encoding="utf-8"))
        statuses = {name: rec["status"] for name, rec in manifest["scripts"].items()}
        self.assertEqual(statuses["transcribe"], "no_speech")
        for name, status in statuses.items():
            if name != "transcribe":
                self.assertEqual(status, "ok", f"{name} recorded status {status}")

    @unittest.skipUnless(
        os.environ.get("PADDLEOCR_ACCESS_TOKEN"),
        "PADDLEOCR_ACCESS_TOKEN required for the real hosted-API OCR test",
    )
    def test_07_screen_ocr_real_api(self):
        summary = self.run_script(
            "screen_ocr", str(self.video),
            "--segments", str(self.out / "data" / "screen_segments.json"),
        )
        self.assertEqual(summary["engine"], "api")
        self.assertEqual(summary["n_screens"], 3)
        self.assertEqual(summary["screens_failed"], 0)
        ocr = json.loads(
            (self.out / "data" / "screen_ocr.json").read_text(encoding="utf-8")
        )
        joined = " ".join(s["full_text"] for s in ocr["screens"])
        for word in ("ONE", "TWO", "THREE"):
            self.assertIn(word, joined.upper().replace(" ", ""))
        frames = list((self.out / "evidence" / "ocr_frames").glob("seg_*.png"))
        self.assertEqual(len(frames), 3)


if __name__ == "__main__":
    unittest.main()
