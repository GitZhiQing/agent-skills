"""Integration test: run the whole ffmpeg-backed pipeline on a synthetic video.

Skipped automatically when ffmpeg (with libx264) is unavailable.
"""

import json
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


if __name__ == "__main__":
    unittest.main()
