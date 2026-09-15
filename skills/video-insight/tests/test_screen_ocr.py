import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from test_common import load_module

JSONL_LINE = json.dumps({
    "result": {"ocrResults": [{"prunedResult": {
        "rec_texts": ["第一行", "SECOND LINE"],
        "rec_scores": [0.98, 0.91],
        "rec_polys": [
            [[10, 200], [300, 200], [300, 240], [10, 240]],
            [[10, 100], [300, 100], [300, 140], [10, 140]],
        ],
    }}]},
}, ensure_ascii=False)


class TestMultipart(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("screen_ocr")

    def test_shape_contains_fields_and_file(self):
        body, content_type = self.mod._multipart(
            {"model": "PP-OCRv5"}, "frame.png", b"\x89PNG", "image/png"
        )
        self.assertIn("multipart/form-data", content_type)
        self.assertIn(b'name="model"\r\n\r\nPP-OCRv5', body)
        self.assertIn(b'filename="frame.png"', body)
        self.assertIn(b"Content-Type: image/png", body)
        self.assertIn(b"\x89PNG", body)


class TestExtractScreenLines(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("screen_ocr")

    def test_lines_sorted_top_to_bottom(self):
        lines = self.mod.extract_screen_lines(
            json.loads(JSONL_LINE)["result"]["ocrResults"][0]
        )
        self.assertEqual([ln["text"] for ln in lines], ["SECOND LINE", "第一行"])
        self.assertEqual(lines[0]["confidence"], 0.91)

    def test_rec_boxes_fallback(self):
        lines = self.mod.extract_screen_lines({"prunedResult": {
            "rec_texts": ["solo"],
            "rec_scores": [0.5],
            "rec_polys": [],
            "rec_boxes": [[1, 2, 3, 4]],
        }})
        self.assertEqual(lines[0]["box"], [[1, 2], [3, 2], [3, 4], [1, 4]])

    def test_empty_page(self):
        self.assertEqual(self.mod.extract_screen_lines({}), [])


class TestPickEngine(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("screen_ocr")

    def test_api_without_token_raises(self):
        with self.assertRaises(RuntimeError):
            self.mod.pick_engine("api", None)

    def test_auto_prefers_api(self):
        self.assertEqual(self.mod.pick_engine("auto", "tok"), ("api", "tok"))
        self.assertEqual(self.mod.pick_engine("auto", None), ("local", None))
        self.assertEqual(self.mod.pick_engine("local", "tok"), ("local", None))


class TestApiFlow(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("screen_ocr")

    def test_submit_returns_job_id(self):
        reply = b'{"code": 0, "data": {"jobId": "j1"}}'
        with mock.patch.object(self.mod, "_http", return_value=reply) as http:
            job_id = self.mod.api_submit("tok", b"img", model="PP-OCRv5")
        self.assertEqual(job_id, "j1")
        body = http.call_args.kwargs["body"]
        self.assertIn(b"name=\"model\"", body)
        self.assertIn(b"optionalPayload", body)

    def test_submit_error_code_raises(self):
        reply = b'{"code": 10007, "msg": "bad model"}'
        with mock.patch.object(self.mod, "_http", return_value=reply):
            with self.assertRaises(RuntimeError):
                self.mod.api_submit("tok", b"img", model="nope")

    def test_wait_until_done(self):
        replies = [
            b'{"code": 0, "data": {"state": "pending"}}',
            b'{"code": 0, "data": {"state": "done", "jobId": "j1"}}',
        ]
        with mock.patch.object(self.mod, "_http", side_effect=replies), \
                mock.patch.object(self.mod.time, "sleep"):
            job = self.mod.api_wait("tok", "j1", timeout=10)
        self.assertEqual(job["state"], "done")

    def test_wait_failed_state_raises(self):
        reply = b'{"code": 0, "data": {"state": "failed", "errorMsg": "boom"}}'
        with mock.patch.object(self.mod, "_http", return_value=reply):
            with self.assertRaises(RuntimeError):
                self.mod.api_wait("tok", "j1", timeout=10)

    def test_result_lines_download_without_bearer(self):
        job = {"resultUrl": {"jsonUrl": "https://bos.example/r.jsonl"}}
        with mock.patch.object(self.mod, "_http", return_value=JSONL_LINE.encode()) as http:
            lines = self.mod.api_result_lines("tok", job)
        self.assertEqual([ln["text"] for ln in lines], ["SECOND LINE", "第一行"])
        # presigned BOS link: the Bearer token must NOT be attached
        self.assertIsNone(http.call_args.args[1])


class TestOcrScreensRecording(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("screen_ocr")

    def test_full_text_confidence_and_error_capture(self):
        with TemporaryDirectory() as tmp:
            frames = [Path(tmp) / "f1.png", Path(tmp) / "f2.png"]
            for frame in frames:
                frame.write_bytes(b"png")
            segments = [
                {"i": 1, "t_start": 0.0, "t_end": 2.0, "grab_at": 1.0, "basis": "still_mid"},
                {"i": 2, "t_start": 2.0, "t_end": 4.0, "grab_at": 3.0, "basis": "still_mid"},
            ]
            good_lines = [{"text": "HELLO", "confidence": 0.9, "box": None}]
            with mock.patch.object(self.mod, "api_submit", side_effect=["j1", "j2"]), \
                    mock.patch.object(self.mod, "api_wait", side_effect=[
                        {"state": "done"},
                        RuntimeError("network hiccup"),
                    ]), \
                    mock.patch.object(self.mod, "api_result_lines", return_value=good_lines), \
                    mock.patch.object(self.mod.time, "sleep"):
                screens = self.mod.ocr_screens(
                    segments, frames, engine_name="api", token="tok",
                    model="PP-OCRv5", lang="ch", timeout=10,
                )
        self.assertEqual(screens[0]["full_text"], "HELLO")
        self.assertEqual(screens[0]["mean_confidence"], 0.9)
        self.assertIn("network hiccup", screens[1]["error"])


if __name__ == "__main__":
    unittest.main()
