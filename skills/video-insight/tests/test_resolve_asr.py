import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from test_common import load_module


class TestResolveAsr(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("resolve_asr")

    def test_env_var_wins(self):
        with TemporaryDirectory() as tmp:
            fake = Path(tmp) / "helper.py"
            fake.write_text("# stub\n")
            with mock.patch.dict(os.environ, {"VIDEO_INSIGHT_ASR_SCRIPT": str(fake)}):
                result = self.mod.resolve_asr()
            self.assertTrue(result["ok"])
            self.assertEqual(result["source"], "env:VIDEO_INSIGHT_ASR_SCRIPT")

    def test_not_found_gives_hint(self):
        with TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"VIDEO_INSIGHT_ASR_SCRIPT": ""}):
                with mock.patch.object(self.mod, "SKILLS_ROOT", Path(tmp)), \
                     mock.patch.object(self.mod, "SCRIPTS_DIR", Path(tmp) / "video-insight" / "scripts"):
                    result = self.mod.resolve_asr()
            self.assertFalse(result["ok"])
            self.assertIn("hint", result)

    def test_find_api_key_in_env_file(self):
        with TemporaryDirectory() as tmp:
            scripts_dir = Path(tmp) / "skill" / "scripts"
            scripts_dir.mkdir(parents=True)
            asr = scripts_dir / "transcribe_volcengine_bigmodel.py"
            asr.write_text("# stub\n")
            (scripts_dir.parent / ".env").write_text("VOLC_BIGMODEL_API_KEY=abc123\n")
            with mock.patch.dict(os.environ, {"VOLC_BIGMODEL_API_KEY": ""}):
                found = self.mod._find_api_key(asr)
            self.assertTrue(found["configured"])
            self.assertIn(".env", found["source"])

    def test_api_key_from_environment(self):
        with TemporaryDirectory() as tmp:
            asr = Path(tmp) / "helper.py"
            with mock.patch.dict(os.environ, {"VOLC_BIGMODEL_API_KEY": "k"}):
                found = self.mod._find_api_key(asr)
            self.assertEqual(found["source"], "environment variable")


if __name__ == "__main__":
    unittest.main()
