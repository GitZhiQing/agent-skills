"""Tests for pipeline.py: idempotent orchestration, the OCR-side screen
transcript assembler, and stats. Integration cases run the real CLI on
synthetic videos (no API keys needed; the real-OCR case skips without a token)."""

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from test_common import load_module

ROOT_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
pipeline = load_module("pipeline")

# Reuse the synthetic text-card builder from the integration suite.
from test_integration import (  # noqa: E402
    FFMPEG,
    FFPROBE,
    _can_encode_h264_aac,
    _find_font,
    _has_drawtext,
    _text_card_filter,
)


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class TestHelpers(unittest.TestCase):
    def test_count_chars_matches_transcribe_rule(self):
        # CJK and alnum count, punctuation/whitespace does not (173-char rule).
        self.assertEqual(pipeline.count_chars("筹码峰，诱多！66"), 5 + 2)

    def test_fmt_ts_srt_format(self):
        self.assertEqual(pipeline.fmt_ts(0.0), "00:00:00,000")
        self.assertEqual(pipeline.fmt_ts(2.5), "00:00:02,500")
        self.assertEqual(pipeline.fmt_ts(61.234), "00:01:01,234")
        self.assertEqual(pipeline.fmt_ts(3661.0), "01:01:01,000")

    def test_readability_three_levels(self):
        self.assertEqual(pipeline.readability_from_confidence(0.95), "清晰")
        self.assertEqual(pipeline.readability_from_confidence(0.70), "低置信")
        self.assertEqual(pipeline.readability_from_confidence(0.30), "不可读")
        self.assertEqual(pipeline.readability_from_confidence(None), "不可读")

    def test_join_grab_ats_ordered_unique(self):
        segments = [{"grab_at": 1.0}, {"grab_at": 3.5}, {"grab_at": 1.0},
                    {"grab_at": 5.0}]
        self.assertEqual(pipeline.join_grab_ats(segments), "1,3.5,5")

    def test_merge_event_anchors_fills_budget_in_time_order(self):
        doc = {
            "params": {"max_screens": 4},
            "segments": [
                {"grab_at": 1.0, "events_in_segment": [0.5]},
                {"grab_at": 3.0, "events_in_segment": [2.5, 2.9]},
                {"grab_at": 5.0, "events_in_segment": []},
            ],
        }
        at_list, counts = pipeline.merge_event_anchors(doc)
        # grab_at first (1,3,5), anchors fill the remaining 1 slot in time order
        self.assertEqual(at_list, "0.5,1,3,5")
        self.assertEqual(counts, {"anchors_added": 1, "anchors_skipped": 2})

    def test_merge_event_anchors_respects_max_screens(self):
        doc = {
            "params": {"max_screens": 3},
            "segments": [
                {"grab_at": 1.0, "events_in_segment": [0.5]},
                {"grab_at": 3.0, "events_in_segment": [2.5, 3.5, 3.9]},
            ],
        }
        at_list, counts = pipeline.merge_event_anchors(doc)
        self.assertEqual(at_list, "0.5,1,3")
        self.assertEqual(counts, {"anchors_added": 1, "anchors_skipped": 3})

    def test_merge_event_anchors_without_anchor_data(self):
        at_list, counts = pipeline.merge_event_anchors(
            {"segments": [{"grab_at": 2.0}]})
        self.assertEqual(at_list, "2")
        self.assertEqual(counts, {"anchors_added": 0, "anchors_skipped": 0})

    def test_run_step_raises_on_failure(self):
        with self.assertRaises(pipeline.StepFailure) as ctx:
            pipeline.run_step("pipeline", ["--help-missing"])  # argparse exits 2
        self.assertEqual(ctx.exception.step, "pipeline")
        self.assertEqual(ctx.exception.exit_code, 2)


class TestAssembleScreenTranscript(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.out = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_inputs(self, mode="event", screens=None):
        segments = []
        for i, (t0, t1, grab) in enumerate(
            [(0.0, 2.0, 1.0), (2.0, 4.0, 3.0), (4.0, 6.0, 5.0)], start=1
        ):
            segments.append({"i": i, "t_start": t0, "t_end": t1,
                             "grab_at": grab, "basis": "still",
                             "still_s": t1 - t0})
        write_json(self.out / "data" / "screen_segments.json",
                   {"mode": mode, "segments": segments,
                    "summary": {"n_screens": len(segments), "mode": mode}})
        ocr_screens = []
        for seg, (text, conf) in zip(segments, screens or [
                ("SCREEN ONE", 0.95), ("SCREEN ONE", 0.93), ("屏 幕 三", 0.62)]
        ):
            ocr_screens.append({
                "i": seg["i"], "t_start": seg["t_start"], "t_end": seg["t_end"],
                "grab_at": seg["grab_at"], "basis": seg["basis"],
                "frame": str(self.out / "evidence" / "ocr_frames" /
                             f"seg_{seg['i']:03d}.png"),
                "lines": [], "full_text": text, "mean_confidence": conf,
            })
        write_json(self.out / "data" / "screen_ocr.json",
                   {"engine": "api", "model": "PP-OCRv5",
                    "screens": ocr_screens,
                    "summary": {"n_screens": 3}})

    def test_merge_adjacent_identical_screens(self):
        self._write_inputs()
        paths = pipeline.assemble_screen_transcript(self.out)
        doc = json.loads((self.out / "transcript.screen.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual([p.name for p in paths],
                         ["transcript.screen.srt", "transcript.screen.json"])
        # Screens 1+2 share text -> one merged row + one remaining row.
        self.assertEqual(len(doc["screens"]), 2)
        merged = doc["screens"][0]
        self.assertEqual(merged["merged_from"], [1, 2])
        self.assertEqual(merged["t_start"], 0.0)
        self.assertEqual(merged["t_end"], 4.0)
        self.assertEqual(doc["merged_pairs"], [[1, 2]])
        self.assertEqual(doc["time_precision"], "exact")

    def test_readability_levels_and_evidence_frames(self):
        self._write_inputs()
        pipeline.assemble_screen_transcript(self.out)
        doc = json.loads((self.out / "transcript.screen.json")
                         .read_text(encoding="utf-8"))
        levels = [s["readability"] for s in doc["screens"]]
        self.assertEqual(levels, ["清晰", "低置信"])
        self.assertEqual(len(doc["screens"][0]["evidence_frames"]), 2)

    def test_uniform_mode_flags_approx(self):
        self._write_inputs(mode="uniform")
        pipeline.assemble_screen_transcript(self.out)
        doc = json.loads((self.out / "transcript.screen.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(doc["time_precision"], "approx")
        self.assertEqual(doc["mode"], "uniform")

    def test_srt_skips_empty_text_and_uses_srt_timestamps(self):
        self._write_inputs(screens=[("SCREEN ONE", 0.95), ("", None),
                                    ("THREE", 0.99)])
        pipeline.assemble_screen_transcript(self.out)
        srt = (self.out / "transcript.screen.srt").read_text(encoding="utf-8")
        self.assertIn("00:00:00,000 --> 00:00:02,000", srt)
        self.assertIn("SCREEN ONE", srt)
        self.assertNotIn("THREE\n\n2", srt)  # empty screen drops a cue number
        doc = json.loads((self.out / "transcript.screen.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(doc["screens"][1]["readability"], "不可读")
        self.assertEqual(doc["screens"][1]["text"], "")

    def test_manifest_records_screen_transcript(self):
        self._write_inputs()
        pipeline.assemble_screen_transcript(self.out)
        manifest = json.loads((self.out / "manifest.json")
                              .read_text(encoding="utf-8"))
        self.assertEqual(manifest["scripts"]["screen_transcript"]["status"], "ok")


class TestStats(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.out = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_voiced_stats_from_transcript_txt_and_meta(self):
        write_json(self.out / "meta.json",
                   {"duration_s": 10.0, "video": {"width": 640}, "audio": {}})
        (self.out / "transcript.txt").write_text("筹码峰诱多，六六！", encoding="utf-8")
        stats = pipeline.voiced_stats(self.out, None)
        self.assertEqual(stats["chars"], 7)  # 筹码峰诱多 + 六六
        self.assertEqual(stats["chars_per_sec"], 0.7)
        self.assertEqual(stats["duration_s"], 10.0)

    def test_voiced_stats_srt_ignores_timestamp_digits(self):
        write_json(self.out / "meta.json", {"duration_s": 10.0})
        (self.out / "transcript.srt").write_text(
            "1\n00:00:00,000 --> 00:00:02,000\n已有转写\n", encoding="utf-8")
        stats = pipeline.voiced_stats(self.out, None)
        self.assertEqual(stats["chars"], 4)

    def test_voiced_stats_prefer_transcribe_info_and_flag_suspect(self):
        write_json(self.out / "meta.json", {"duration_s": 33.3})
        stats = pipeline.voiced_stats(
            self.out, {"chars": 173, "suspect_no_speech": False})
        self.assertEqual(stats["chars"], 173)
        self.assertEqual(stats["chars_per_sec"], 5.2)
        self.assertNotIn("suspect_no_speech", stats)

    def test_screen_stats(self):
        write_json(self.out / "data" / "screen_segments.json",
                   {"mode": "event",
                    "segments": [
                        {"i": 1, "t_start": 0.0, "t_end": 2.0, "grab_at": 1.0},
                        {"i": 2, "t_start": 2.0, "t_end": 6.0, "grab_at": 4.0},
                    ]})
        write_json(self.out / "transcript.screen.json",
                   {"screens": [{"text": "SCREEN ONE"}, {"text": "屏二"}]})
        stats = pipeline.screen_stats(self.out)
        self.assertEqual(stats["n_screens"], 2)
        self.assertEqual(stats["dwell_s"], [2.0, 4.0])
        self.assertEqual(stats["mode"], "event")
        self.assertEqual(stats["total_text_chars"], 9 + 2)

    def test_screen_stats_passthrough_summary_facts(self):
        write_json(self.out / "data" / "screen_segments.json",
                   {"mode": "uniform",
                    "params": {"max_screens": 60},
                    "segments": [
                        {"i": 1, "t_start": 0.0, "t_end": 2.0, "grab_at": 1.0,
                         "events_in_segment": [0.5]},
                        {"i": 2, "t_start": 2.0, "t_end": 4.0, "grab_at": 3.0,
                         "events_in_segment": []},
                    ],
                    "summary": {"n_screens": 2, "mode": "uniform",
                                "n_events": 78, "n_stills": 0,
                                "mean_screen_s": 2.0, "max_screen_s": 2.0,
                                "longest_still_s": None}})
        stats = pipeline.screen_stats(self.out)
        self.assertEqual(stats["n_events"], 78)
        self.assertEqual(stats["n_stills"], 0)
        self.assertEqual(stats["mean_screen_s"], 2.0)
        self.assertEqual(stats["max_screen_s"], 2.0)
        self.assertIsNone(stats["longest_still_s"])

    def test_screen_stats_without_summary_stays_clean(self):
        write_json(self.out / "data" / "screen_segments.json",
                   {"mode": "event",
                    "segments": [
                        {"i": 1, "t_start": 0.0, "t_end": 2.0, "grab_at": 1.0},
                    ]})
        stats = pipeline.screen_stats(self.out)
        for key in ("n_events", "n_stills", "mean_screen_s", "max_screen_s",
                    "longest_still_s"):
            self.assertNotIn(key, stats)


def run_pipeline(*argv, timeout=600):
    return subprocess.run(
        [sys.executable, str(ROOT_SCRIPTS / "pipeline.py"), *argv],
        capture_output=True, timeout=timeout,
    )


@unittest.skipUnless(
    FFMPEG and FFPROBE and _can_encode_h264_aac() and _has_drawtext()
    and _find_font(),
    "ffmpeg with libx264 + drawtext + a font required",
)
class TestPipelineNoSpeechFrames(unittest.TestCase):
    """Text-card video through the whole CLI: no_speech -> frames mode."""

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
            capture_output=True, timeout=120,
        )
        assert cls.video.exists() and cls.video.stat().st_size > 0
        cls.out = cls.root / "out"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_01_collect_branch_frames(self):
        proc = run_pipeline(str(self.video), "--tier", "L1",
                            "--screen-mode", "frames",
                            "--output-dir", str(self.out))
        self.assertEqual(proc.returncode, 0,
                         proc.stderr.decode("utf-8", "replace")[-2000:])
        report = json.loads(proc.stdout.decode("utf-8", "replace"))
        self.assertEqual(report["branch"], "no_speech")
        self.assertEqual(report["steps"]["transcribe"], "no_speech")
        for key in ("probe", "extract_frames", "detect_changes",
                    "screen_segments", "grab_frames"):
            self.assertEqual(report["steps"][key], "ok", key)
        self.assertEqual(report["stats"]["n_screens"], 3)
        # frames mode leaves the transcript to the model, but grabs every screen
        keys = list((self.out / "evidence" / "keyframes").glob("screen_*s.jpg"))
        self.assertEqual(len(keys), 3)
        self.assertFalse((self.out / "transcript.screen.json").exists())
        manifest = json.loads((self.out / "manifest.json")
                              .read_text(encoding="utf-8"))
        switch = manifest["declaration"]["no_speech_switch"]
        self.assertEqual(switch["detected"], "no_audio_track")
        self.assertEqual(switch["by"], "pipeline")
        self.assertTrue(any("事后目检" in n for n in report["notes"]))

    def test_02_rerun_idempotent_all_skipped(self):
        proc = run_pipeline(str(self.video), "--tier", "L1",
                            "--screen-mode", "frames",
                            "--output-dir", str(self.out))
        self.assertEqual(proc.returncode, 0)
        report = json.loads(proc.stdout.decode("utf-8", "replace"))
        for key, value in report["steps"].items():
            # transcribe resumes as its recorded branch signal, not "skipped"
            expected = "no_speech" if key == "transcribe" else "skipped"
            self.assertEqual(value, expected, key)


@unittest.skipUnless(
    FFMPEG and FFPROBE and _can_encode_h264_aac() and _has_drawtext()
    and _find_font(),
    "ffmpeg with libx264 + drawtext + a font required",
)
class TestPipelineL2(unittest.TestCase):
    """Voiced L2 with a pre-seeded transcript: no API key needed."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.video = cls.root / "voiced.mp4"
        subprocess.run(
            [
                FFMPEG, "-loglevel", "error",
                "-f", "lavfi", "-i", "testsrc2=duration=3:size=320x240:rate=30",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-y", str(cls.video),
            ],
            capture_output=True, timeout=120,
        )
        cls.out = cls.root / "out"
        cls.out.mkdir(parents=True)
        (cls.out / "transcript.srt").write_text(
            "1\n00:00:00,000 --> 00:00:02,000\n你好世界\n", encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_l2_collects_base_evidence(self):
        proc = run_pipeline(str(self.video), "--tier", "L2",
                            "--output-dir", str(self.out))
        self.assertEqual(proc.returncode, 0,
                         proc.stderr.decode("utf-8", "replace")[-2000:])
        report = json.loads(proc.stdout.decode("utf-8", "replace"))
        self.assertEqual(report["tier"], "L2")
        self.assertEqual(report["branch"], "voiced")
        self.assertEqual(report["steps"]["transcribe"], "skipped")
        for key in ("extract_frames", "detect_changes", "audio_probe"):
            self.assertEqual(report["steps"][key], "ok", key)
        self.assertEqual(report["stats"]["chars"], 4)
        self.assertTrue((self.out / "data" / "audio.json").exists())
        self.assertTrue(any("拼版检查点" in n for n in report["ai_next"]))


@unittest.skipUnless(
    FFMPEG and FFPROBE and _can_encode_h264_aac() and _has_drawtext()
    and _find_font(),
    "ffmpeg with libx264 + drawtext + a font required",
)
class TestPipelineL2NoAudioTrack(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.video = cls.root / "cards.mp4"
        subprocess.run(
            [
                FFMPEG, "-loglevel", "error",
                "-f", "lavfi", "-i", "color=black:size=640x360:rate=30:duration=6",
                "-vf", _text_card_filter(_find_font().replace(":", r"\:")),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-y", str(cls.video),
            ],
            capture_output=True, timeout=120,
        )
        cls.out = cls.root / "out"
        cls.out.mkdir(parents=True)
        (cls.out / "transcript.srt").write_text(
            "1\n00:00:00,000 --> 00:00:02,000\n预置文案\n", encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_audio_probe_skips_without_audio_track(self):
        proc = run_pipeline(str(self.video), "--tier", "L2",
                            "--output-dir", str(self.out))
        self.assertEqual(proc.returncode, 0,
                         proc.stderr.decode("utf-8", "replace")[-2000:])
        report = json.loads(proc.stdout.decode("utf-8", "replace"))
        self.assertEqual(report["steps"]["audio_probe"],
                         "skipped_no_audio_track")


class TestPipelineTranscriptOnly(unittest.TestCase):
    def test_transcript_input_l1_then_l2_refused(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            srt = root / "given.srt"
            srt.write_text("1\n00:00:00,000 --> 00:00:02,000\n已有转写\n",
                           encoding="utf-8")
            out = root / "out"
            proc = run_pipeline(str(srt), "--tier", "L1",
                                "--output-dir", str(out))
            self.assertEqual(proc.returncode, 0)
            report = json.loads(proc.stdout.decode("utf-8", "replace"))
            self.assertEqual(report["branch"], "transcript_only")
            self.assertEqual(report["steps"]["transcript_input"], "ok")
            self.assertEqual(report["stats"]["chars"], 4)
            self.assertTrue((out / "transcript.srt").exists())

            proc2 = run_pipeline(str(srt), "--tier", "L2",
                                 "--output-dir", str(out))
            self.assertEqual(proc2.returncode, 1)
            error = json.loads(proc2.stdout.decode("utf-8", "replace"))
            self.assertIn("L2", error["error"])

    def test_missing_input_fails_cleanly(self):
        with TemporaryDirectory() as tmp:
            proc = run_pipeline(str(Path(tmp) / "nope.mp4"), "--tier", "L1",
                                "--output-dir", str(Path(tmp) / "out"))
            self.assertEqual(proc.returncode, 1)
            error = json.loads(proc.stdout.decode("utf-8", "replace"))
            self.assertIn("not found", error["error"])


class TestBatchHelpers(unittest.TestCase):
    def test_assign_slugs_suffix_on_clash(self):
        assigned = pipeline.assign_slugs(
            ["dirA/demo.srt", "dirB/demo.srt", "other.mp4", "dirC/demo.srt"])
        slugs = [slug for _, slug, _ in assigned]
        self.assertEqual(slugs, ["demo", "demo-2", "other", "demo-3"])
        self.assertEqual([p.as_posix() for _, _, p in assigned],
                         ["demo", "demo-2", "other", "demo-3"])

    def test_read_batch_file_skips_comments_and_blanks(self):
        with TemporaryDirectory() as tmp:
            batch = Path(tmp) / "list.txt"
            batch.write_text(
                "# comment line\n\n  a.mp4  \nhttps://b23.tv/xyz\n#another\nb.srt\n",
                encoding="utf-8")
            self.assertEqual(pipeline.read_batch_file(batch),
                             ["a.mp4", "https://b23.tv/xyz", "b.srt"])


@unittest.skipUnless(
    FFMPEG and FFPROBE and _can_encode_h264_aac() and _has_drawtext()
    and _find_font(),
    "ffmpeg with libx264 + drawtext + a font required",
)
class TestPipelineBatch(unittest.TestCase):
    """Mixed batch through the real CLI: transcript + text cards + failures."""

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
            capture_output=True, timeout=120,
        )
        assert cls.video.exists() and cls.video.stat().st_size > 0
        cls.srt = cls.root / "given.srt"
        cls.srt.write_text(
            "1\n00:00:00,000 --> 00:00:02,000\n第一条的已有转写\n",
            encoding="utf-8")
        cls.batch_root = cls.root / "batch"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_01_mixed_batch_one_command(self):
        proc = run_pipeline(str(self.srt), str(self.video), "--tier", "L1",
                            "--output-dir", str(self.batch_root))
        self.assertEqual(proc.returncode, 0,
                         proc.stderr.decode("utf-8", "replace")[-2000:])
        report = json.loads(proc.stdout.decode("utf-8", "replace"))
        self.assertEqual(report["batch"]["n"], 2)
        self.assertEqual(report["batch"]["ok"], 2)
        self.assertEqual(report["batch"]["failed"], 0)
        self.assertEqual(sorted(report["batch"]["branches"]),
                         ["no_speech", "transcript_only"])
        by_slug = {r["slug"]: r for r in report["results"]}
        self.assertEqual(by_slug["given"]["status"], "ok")
        self.assertEqual(by_slug["given"]["stats"]["chars"], 8)
        self.assertEqual(by_slug["textcards"]["branch"], "no_speech")
        self.assertEqual(by_slug["textcards"]["stats"]["n_screens"], 3)
        # per-item archives are isolated under <batch-root>/<slug>/
        self.assertTrue((self.batch_root / "given" / "transcript.srt").exists())
        self.assertTrue((self.batch_root / "textcards" / "manifest.json").exists())
        self.assertEqual(len(list((self.batch_root / "textcards" /
                                   "evidence" / "keyframes")
                                  .glob("screen_*s.jpg"))), 3)
        # the batch summary is archived next to the item directories
        saved = json.loads((self.batch_root / "batch-report.json")
                           .read_text(encoding="utf-8"))
        self.assertEqual(saved["batch"]["n"], 2)
        self.assertTrue(any("跨视频对比" in n for n in report["ai_next"]))

    def test_02_rerun_batch_idempotent(self):
        proc = run_pipeline(str(self.srt), str(self.video), "--tier", "L1",
                            "--output-dir", str(self.batch_root))
        self.assertEqual(proc.returncode, 0)
        report = json.loads(proc.stdout.decode("utf-8", "replace"))
        for result in report["results"]:
            for step, value in result["steps"].items():
                expected = "no_speech" if step == "transcribe" else "skipped"
                self.assertEqual(value, expected, f"{result['slug']}.{step}")

    def test_03_failure_isolation(self):
        missing = self.root / "nope.mp4"
        proc = run_pipeline(str(missing), str(self.srt), "--tier", "L1",
                            "--output-dir", str(self.root / "batch2"))
        self.assertEqual(proc.returncode, 1)  # honest exit when any item fails
        report = json.loads(proc.stdout.decode("utf-8", "replace"))
        self.assertEqual(report["batch"]["ok"], 1)
        self.assertEqual(report["batch"]["failed"], 1)
        failed = [r for r in report["results"] if r["status"] == "failed"][0]
        self.assertIn("not found", failed["error"])
        ok = [r for r in report["results"] if r["status"] == "ok"][0]
        self.assertEqual(ok["slug"], "given")

    def test_04_batch_list_file_and_jobs(self):
        other = self.root / "other.srt"
        other.write_text("1\n00:00:00,000 --> 00:00:01,000\n第二条\n",
                         encoding="utf-8")
        batch_file = self.root / "list.txt"
        batch_file.write_text(
            f"# two transcript items, run concurrently\n{self.srt}\n\n{other}\n",
            encoding="utf-8")
        proc = run_pipeline("--batch", str(batch_file), "--tier", "L1",
                            "--jobs", "2",
                            "--output-dir", str(self.root / "batch3"))
        self.assertEqual(proc.returncode, 0,
                         proc.stderr.decode("utf-8", "replace")[-2000:])
        report = json.loads(proc.stdout.decode("utf-8", "replace"))
        self.assertEqual(report["batch"]["jobs"], 2)
        self.assertEqual(report["batch"]["ok"], 2)
        self.assertEqual(sorted(r["slug"] for r in report["results"]),
                         ["given", "other"])


if __name__ == "__main__":
    unittest.main()
