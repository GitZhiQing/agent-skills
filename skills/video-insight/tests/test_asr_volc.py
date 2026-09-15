import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from test_common import load_module


def _response(body=b"{}", status="20000000", message=""):
    return (body, status, message)


class TestNormalize(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("asr_volc")

    def test_ms_to_srt(self):
        f = self.mod.ms_to_srt
        self.assertEqual(f(0), "00:00:00,000")
        self.assertEqual(f(3723456), "01:02:03,456")
        self.assertEqual(f(59_999), "00:00:59,999")
        self.assertEqual(f(-5), "00:00:00,000")  # clamped

    def test_to_srt_renumbers_and_skips_empty(self):
        result = {"result": {"utterances": [
            {"text": "第一句", "start_time": 0, "end_time": 1500},
            {"text": "  ", "start_time": 1500, "end_time": 2000},
            {"text": "第二句", "start_time": 2000, "end_time": 3500},
        ]}}
        srt = self.mod.to_srt(result)
        self.assertIn("1\n00:00:00,000 --> 00:00:01,500\n第一句", srt)
        self.assertIn("2\n00:00:02,000 --> 00:00:03,500\n第二句", srt)

    def test_to_srt_empty_and_to_text(self):
        self.assertEqual(self.mod.to_srt({}), "")
        self.assertEqual(self.mod.to_srt({"result": {}}), "")
        self.assertEqual(self.mod.to_text({"result": {"text": " 你好。 "}}), "你好。")
        self.assertEqual(self.mod.to_text({}), "")


class TestPayload(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("asr_volc")

    def test_url_audio_uses_url_field(self):
        payload = self.mod.build_payload(
            "https://example.com/a.mp3", language=None, hotwords=None,
            resource_id="volc.seedasr.auc",
        )
        self.assertEqual(payload["audio"], {"url": "https://example.com/a.mp3"})
        request = payload["request"]
        self.assertEqual(request["model_name"], "volc.seedasr.auc")
        self.assertTrue(request["enable_punc"])
        self.assertTrue(request["enable_itn"])
        self.assertNotIn("corpus", request)
        self.assertNotIn("language", request)

    def test_local_file_uses_base64_data(self):
        with TemporaryDirectory() as tmp:
            audio = Path(tmp) / "audio.mp3"
            audio.write_bytes(b"abc")
            payload = self.mod.build_payload(
                audio, language="zh-CN", hotwords=None,
                resource_id="volc.seedasr.auc",
            )
        import base64
        self.assertEqual(payload["audio"]["format"], "mp3")
        self.assertEqual(payload["audio"]["data"], base64.b64encode(b"abc").decode())
        self.assertEqual(payload["request"]["language"], "zh-CN")

    def test_local_file_too_large_refused(self):
        with TemporaryDirectory() as tmp:
            audio = Path(tmp) / "big.mp3"
            audio.write_bytes(b"x" * 32)
            with mock.patch.object(self.mod, "MAX_AUDIO_BYTES", 10):
                with self.assertRaises(RuntimeError):
                    self.mod.build_payload(
                        audio, language=None, hotwords=None,
                        resource_id="volc.seedasr.auc",
                    )

    def test_hotwords_become_corpus_context(self):
        payload = self.mod.build_payload(
            "https://e.com/a.mp3", language=None, hotwords="筹码峰, K线,诱多",
            resource_id="volc.seedasr.auc",
        )
        corpus = payload["request"]["corpus"]
        self.assertIn("context", corpus)
        self.assertIn("筹码峰", corpus["context"])
        self.assertIn("K线", corpus["context"])
        self.assertIn("诱多", corpus["context"])


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("asr_volc")

    def test_missing_key_raises_with_guidance(self):
        with mock.patch.object(self.mod, "get_config", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                self.mod.api_config()
        self.assertIn("console.volcengine.com", str(ctx.exception))

    def test_defaults_from_config(self):
        values = {
            "VOLC_BIGMODEL_API_KEY": "k",
            "VOLC_BIGMODEL_RESOURCE_ID": None,
            "VOLC_BIGMODEL_API_BASE": None,
        }
        with mock.patch.object(self.mod, "get_config",
                               side_effect=lambda n, d=None: values.get(n) or d):
            cfg = self.mod.api_config()
        self.assertEqual(cfg["key"], "k")
        self.assertEqual(cfg["resource_id"], "volc.seedasr.auc")
        self.assertEqual(cfg["api_base"], "https://openspeech.bytedance.com")


class TestSubmitQuery(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("asr_volc")
        self.cfg = {
            "key": "k",
            "resource_id": "volc.seedasr.auc",
            "api_base": "https://openspeech.bytedance.com",
        }

    def test_submit_headers_and_request_id(self):
        captured = {}

        def fake_post(url, headers, body, **kwargs):
            captured["url"] = url
            captured["headers"] = headers
            captured["body"] = body
            return _response()

        with mock.patch.object(self.mod, "_post_json", side_effect=fake_post):
            request_id = self.mod.submit(
                "https://e.com/a.mp3", cfg=self.cfg, request_id="rid-1"
            )
        self.assertEqual(request_id, "rid-1")
        self.assertEqual(
            captured["url"],
            "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit",
        )
        self.assertEqual(captured["headers"]["X-Api-Key"], "k")
        self.assertEqual(captured["headers"]["X-Api-Resource-Id"], "volc.seedasr.auc")
        self.assertEqual(captured["headers"]["X-Api-Request-Id"], "rid-1")
        self.assertEqual(captured["headers"]["X-Api-Sequence"], "-1")

    def test_submit_generates_request_id_and_forwards_payload(self):
        import json
        captured = {}

        def fake_post(url, headers, body, **kwargs):
            captured["payload"] = json.loads(body)
            return _response()

        with mock.patch.object(self.mod, "_post_json", side_effect=fake_post):
            request_id = self.mod.submit(
                "https://e.com/a.mp3", language="zh-CN", hotwords="K线",
                cfg=self.cfg,
            )
        self.assertTrue(request_id)
        self.assertEqual(captured["payload"]["audio"]["url"], "https://e.com/a.mp3")
        self.assertIn("corpus", captured["payload"]["request"])

    def test_submit_rejects_error_status(self):
        with mock.patch.object(
            self.mod, "_post_json",
            return_value=_response(b'{"err":1}', "45000001", "bad params"),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                self.mod.submit("https://e.com/a.mp3", cfg=self.cfg)
        self.assertIn("45000001", str(ctx.exception))
        self.assertIn("bad params", str(ctx.exception))

    def test_wait_result_success_returns_json(self):
        body = b'{"result": {"text": "hi"}}'

        def fake_post(url, headers, body_, **kwargs):
            self.assertIn("/query", url)
            self.assertEqual(headers["X-Api-Request-Id"], "rid-1")
            return _response(body)

        with mock.patch.object(self.mod, "_post_json", side_effect=fake_post):
            result = self.mod.wait_result("rid-1", cfg=self.cfg)
        self.assertEqual(result["result"]["text"], "hi")

    def test_wait_result_polls_with_backoff(self):
        statuses = [
            _response(status="20000001"),
            _response(status="20000002"),
            _response(b'{"result": {}}'),
        ]
        sleeps = []
        with mock.patch.object(self.mod, "_post_json",
                               side_effect=statuses), \
                mock.patch.object(self.mod.time, "sleep",
                                  side_effect=sleeps.append):
            self.mod.wait_result("rid-1", cfg=self.cfg)
        self.assertEqual(sleeps, [2.0, 2.6])

    def test_wait_result_no_speech_status_returns_body(self):
        """Real-API contract: 20000003 = completed but no valid speech."""
        body = b'{"audio_info":{"duration":2088},"result":{"text":""}}'
        with mock.patch.object(
            self.mod, "_post_json",
            return_value=(body, "20000003", "[Normal silence audio]"),
        ):
            result = self.mod.wait_result("rid-1", cfg=self.cfg)
        self.assertEqual(result["result"]["text"], "")

    def test_wait_result_error_status_raises(self):
        with mock.patch.object(
            self.mod, "_post_json",
            return_value=_response(b"", "45000002", "quota exceeded"),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                self.mod.wait_result("rid-1", cfg=self.cfg)
        self.assertIn("quota exceeded", str(ctx.exception))

    def test_wait_result_timeout(self):
        with mock.patch.object(
            self.mod, "_post_json", return_value=_response(status="20000001")
        ), mock.patch.object(self.mod.time, "sleep"):
            with self.assertRaises(TimeoutError):
                self.mod.wait_result("rid-1", cfg=self.cfg, timeout=0.0)

    def test_transcribe_audio_end_to_end_mocked(self):
        raw = {"result": {
            "text": "你好",
            "utterances": [{"text": "你好", "start_time": 0, "end_time": 900}],
        }}
        with mock.patch.object(self.mod, "api_config", return_value=self.cfg), \
                mock.patch.object(
                    self.mod, "submit", return_value="rid-9"
                ) as fake_submit, \
                mock.patch.object(
                    self.mod, "wait_result", return_value=raw
                ) as fake_wait:
            out = self.mod.transcribe_audio("https://e.com/a.mp3", hotwords="K线")
        fake_submit.assert_called_once()
        self.assertEqual(fake_submit.call_args.kwargs["hotwords"], "K线")
        fake_wait.assert_called_once()
        self.assertEqual(fake_wait.call_args.args, ("rid-9",))
        self.assertEqual(out["txt"], "你好")
        self.assertIn("00:00:00,000 --> 00:00:00,900", out["srt"])
        self.assertEqual(out["request_id"], "rid-9")


if __name__ == "__main__":
    unittest.main()
