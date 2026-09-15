import unittest

from test_common import load_module


class TestParseShowinfo(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("extract_frames")

    def test_real_format(self):
        stderr = (
            "[Parsed_showinfo_1 @ 0x22d4e004340] n:   0 pts:       0 pts_time:0            pos:   -1 fps:0.0 q:0.0\n"
            "[Parsed_showinfo_1 @ 0x22d4e004340] n:   1 pts:    5120 pts_time:1            pos:  512\n"
            "[Parsed_showinfo_1 @ 0x22d4e004340] n:  12 pts:   61440 pts_time:12           pos: 6144\n"
        )
        stamps = self.mod.parse_showinfo(stderr)
        self.assertEqual(stamps, {0: 0.0, 1: 1.0, 12: 12.0})

    def test_fractional_times(self):
        stderr = "n:   3 pts:   15360 pts_time:3.000000\n"
        self.assertEqual(self.mod.parse_showinfo(stderr), {3: 3.0})


class TestCellsFor(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("extract_frames")

    def test_mapping_and_padding(self):
        from pathlib import Path

        images = [Path("overview_01.jpg"), Path("overview_02.jpg")]
        stamps = {g: float(g) for g in range(10)}  # 10 real frames, 6 padded
        manifest = self.mod.cells_for(images, stamps, cells_per_image=8)
        self.assertEqual(manifest[0]["file"], "overview_01.jpg")
        self.assertEqual(manifest[0]["cells"][5]["t_exact"], 5.0)
        self.assertEqual(manifest[1]["cells"][0]["t_exact"], 8.0)
        self.assertIsNone(manifest[1]["cells"][2]["t_exact"])  # padded cell
        self.assertEqual(manifest[1]["cells"][2]["frame_index"], 10)


class TestParseCrop(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("extract_frames")

    def test_valid(self):
        self.assertEqual(self.mod.parse_crop("720x120+0+915"), "720:120:0:915")

    def test_invalid(self):
        with self.assertRaises(ValueError):
            self.mod.parse_crop("720x120")


if __name__ == "__main__":
    unittest.main()
