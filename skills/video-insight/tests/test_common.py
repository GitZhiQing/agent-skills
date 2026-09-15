import importlib.util
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class TestSlugify(unittest.TestCase):
    def setUp(self):
        self.common = load_module("_common")

    def test_plain(self):
        self.assertEqual(self.common.slugify("2.mp4"), "2")

    def test_spaces_and_punctuation(self):
        self.assertEqual(self.common.slugify("my video (final).mp4"), "my_video_final")

    def test_cjk_kept(self):
        self.assertEqual(self.common.slugify("视频一.mp4"), "视频一")

    def test_fallback(self):
        self.assertEqual(self.common.slugify("???"), "video")


class TestManifest(unittest.TestCase):
    def setUp(self):
        self.common = load_module("_common")

    def test_ok_record(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "out.bin"
            target.write_bytes(b"x")
            record = self.common.update_manifest(tmp_path, "probe", status="ok", outputs=[target])
            self.assertEqual(record["status"], "ok")
            manifest = self.common.read_json(tmp_path / "manifest.json")
            self.assertEqual(manifest["scripts"]["probe"]["status"], "ok")

    def test_missing_output_flips_status(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            record = self.common.update_manifest(
                tmp_path, "extract", status="ok", outputs=[tmp_path / "nope.jpg"]
            )
            self.assertEqual(record["status"], "missing_files")
            self.assertEqual(len(record["missing"]), 1)

    def test_second_run_keeps_first(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            f1 = tmp_path / "a.json"; f1.write_text("{}")
            f2 = tmp_path / "b.json"; f2.write_text("{}")
            self.common.update_manifest(tmp_path, "probe", status="ok", outputs=[f1])
            self.common.update_manifest(tmp_path, "palette", status="ok", outputs=[f2])
            manifest = self.common.read_json(tmp_path / "manifest.json")
            self.assertEqual(set(manifest["scripts"]), {"probe", "palette"})

    def test_empty_file_counts_as_missing(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            empty = tmp_path / "empty.jpg"
            empty.write_bytes(b"")
            record = self.common.update_manifest(tmp_path, "x", status="ok", outputs=[empty])
            self.assertEqual(record["status"], "missing_files")


if __name__ == "__main__":
    unittest.main()
