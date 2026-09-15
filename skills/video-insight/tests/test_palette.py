import unittest
from collections import Counter

from test_common import load_module


class TestParseCrop(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("palette")

    def test_valid(self):
        self.assertEqual(self.mod.parse_crop("500x500+110+230"), (500, 500, 110, 230))

    def test_invalid(self):
        with self.assertRaises(ValueError):
            self.mod.parse_crop("500x500")
        with self.assertRaises(ValueError):
            self.mod.parse_crop("foo")


class TestClusterColors(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("palette")

    def counter(self, colors):
        return Counter(colors)

    def test_total_pixels_preserved(self):
        # every pixel lands in exactly one cluster: shares must not exceed 1.0
        colors = [(255, 255, 255)] * 100 + [(238, 84, 76)] * 10
        clusters = self.mod.cluster_colors(self.counter(colors), merge_dist=16)
        self.assertEqual(sum(c["pixels"] for c in clusters), 110)

    def test_near_colors_merge_with_mode_representative(self):
        colors = [(238, 84, 76)] * 5 + [(237, 83, 75)] * 2 + [(37, 168, 125)] * 3
        clusters = self.mod.cluster_colors(self.counter(colors), merge_dist=16)
        self.assertEqual(len(clusters), 2)
        top = clusters[0]
        self.assertEqual(top["rgb"], (238, 84, 76))
        self.assertEqual(top["pixels"], 7)
        self.assertEqual(clusters[1]["rgb"], (37, 168, 125))

    def test_distant_colors_stay_separate(self):
        colors = [(238, 84, 76)] * 5 + [(37, 168, 125)] * 5
        clusters = self.mod.cluster_colors(self.counter(colors), merge_dist=16)
        self.assertEqual(len(clusters), 2)


if __name__ == "__main__":
    unittest.main()
