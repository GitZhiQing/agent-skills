import unittest

from test_common import load_module


def frames_from(pairs):
    """(t, v) pairs -> frames list like collect_frames produces."""
    return [{"t": t, "v": v} for t, v in pairs]


class TestMergeEvents(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("detect_changes")

    def test_two_mp4_burst_pattern(self):
        # Expected values are 2.mp4 (33.3s, 720x1280, 30fps K-line short):
        # 0.37(3.3) 1.93(4.3) 2.97(2.4) 4.57(7.8) 9.63(1.9) 9.87(2.9)
        # 12.00(0.8)+12.10(1.8) 14.80–14.97(3.0–4.7) 18.20(0.7) 20.37(3.7)
        # bursts span several consecutive frames (30fps -> 0.033s apart)
        frames = frames_from([
            (0.37, 3.3), (1.93, 4.3), (2.13, 1.2), (2.17, 0.9), (2.23, 0.9),
            (2.27, 0.6), (2.33, 0.6), (2.97, 2.4), (4.57, 7.8),
            (9.63, 1.9), (9.87, 2.9),
            (12.00, 0.8), (12.03, 0.9), (12.07, 1.2), (12.10, 1.8),
            (14.80, 3.0), (14.83, 2.5), (14.87, 3.4), (14.90, 3.9), (14.93, 3.6), (14.97, 4.7),
            (18.20, 0.7), (20.37, 3.7),
        ])
        events = self.mod.merge_events(frames, threshold=0.55, merge_gap=0.15)
        starts = [round(e["t_start"], 2) for e in events]
        peaks = [round(e["peak"], 1) for e in events]
        self.assertEqual(
            starts,
            [0.37, 1.93, 2.13, 2.97, 4.57, 9.63, 9.87, 12.0, 14.8, 18.2, 20.37],
        )
        self.assertEqual(
            peaks,
            [3.3, 4.3, 1.2, 2.4, 7.8, 1.9, 2.9, 1.8, 4.7, 0.7, 3.7],
        )

    def test_gap_rule(self):
        # 0.10s apart merges into one event; 0.20s apart stays separate
        # (2.mp4 keeps 6.40/6.60 and 9.63/9.87 as distinct events)
        frames = frames_from([(1.0, 2.0), (1.1, 1.0), (2.0, 2.0), (2.2, 1.0)])
        events = self.mod.merge_events(frames, threshold=0.55, merge_gap=0.15)
        self.assertEqual([e["t_start"] for e in events], [1.0, 2.0, 2.2])

    def test_threshold_excludes_small_changes(self):
        frames = frames_from([(1.0, 0.5), (2.0, 0.56)])
        events = self.mod.merge_events(frames, threshold=0.55, merge_gap=0.15)
        self.assertEqual([e["t_start"] for e in events], [2.0])


class TestFindStills(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("detect_changes")

    def test_still_detected(self):
        frames = frames_from([(0.0, 2.0)] + [(t, 0.02) for t in (1.0, 2.0, 3.0, 4.0)] + [(5.0, 2.0)])
        stills = self.mod.find_stills(frames, still_threshold=0.1, min_still=1.0)
        self.assertEqual(len(stills), 1)
        self.assertEqual(stills[0]["t_start"], 1.0)
        self.assertEqual(stills[0]["duration_s"], 3.0)

    def test_short_run_ignored(self):
        frames = frames_from([(0.0, 2.0), (1.0, 0.02), (1.5, 2.0)])
        stills = self.mod.find_stills(frames, still_threshold=0.1, min_still=1.0)
        self.assertEqual(stills, [])

    def test_still_extends_to_end(self):
        frames = frames_from([(0.0, 2.0)] + [(t, 0.02) for t in (1.0, 2.0, 3.0)])
        stills = self.mod.find_stills(frames, still_threshold=0.1, min_still=1.0)
        self.assertEqual(len(stills), 1)
        self.assertEqual(stills[0]["t_end"], 3.0)


if __name__ == "__main__":
    unittest.main()
