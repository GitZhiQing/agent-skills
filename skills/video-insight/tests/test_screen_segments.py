import unittest

from test_common import load_module


def ev(t0, t1, peak=1.0):
    return {"t_start": t0, "t_end": t1, "peak": peak, "peak_t": t0, "frames": 1}


def still(t0, t1):
    return {"t_start": t0, "t_end": t1, "duration_s": round(t1 - t0, 2)}


class TestClusterEvents(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("screen_segments")

    def test_dense_burst_merges(self):
        clusters = self.mod.cluster_events(
            [ev(2.2, 2.3), ev(2.5, 2.6), ev(2.8, 2.9)], min_screen_gap=2.0
        )
        self.assertEqual(len(clusters), 1)
        self.assertEqual((clusters[0]["t_start"], clusters[0]["t_end"]), (2.2, 2.9))
        self.assertEqual(clusters[0]["n_events"], 3)

    def test_gap_splits_clusters(self):
        clusters = self.mod.cluster_events(
            [ev(2.2, 2.3), ev(5.0, 5.1)], min_screen_gap=2.0
        )
        self.assertEqual(len(clusters), 2)


class TestBuildSegments(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("screen_segments")
        self.kwargs = dict(min_screen_gap=2.0, uniform_interval=2.0, max_screens=60)

    def test_three_stills_three_screens(self):
        payload = self.mod.build_segments(
            {
                "duration_s": 6.0,
                "events": [ev(1.95, 2.05), ev(3.95, 4.05)],
                "stills": [still(0.1, 1.9), still(2.1, 3.9), still(4.1, 5.9)],
            },
            **self.kwargs,
        )
        self.assertEqual(payload["mode"], "event")
        segments = payload["segments"]
        self.assertEqual(len(segments), 3)
        # boundaries snap to the departure events, not gap midpoints
        self.assertEqual([s["t_start"] for s in segments], [0.0, 1.95, 3.95])
        self.assertEqual(segments[-1]["t_end"], 6.0)
        for seg in segments:
            self.assertEqual(seg["basis"], "still_mid")
            self.assertTrue(seg["t_start"] <= seg["grab_at"] <= seg["t_end"])

    def test_leading_typewriter_becomes_own_screen(self):
        payload = self.mod.build_segments(
            {
                "duration_s": 6.0,
                "events": [ev(0.5, 0.6), ev(1.0, 1.1), ev(1.6, 1.8), ev(3.9, 4.0)],
                "stills": [still(4.0, 5.5)],
            },
            **self.kwargs,
        )
        segments = payload["segments"]
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0]["basis"], "event_settle")
        self.assertEqual(segments[0]["grab_at"], 1.8)  # most complete moment
        self.assertEqual(segments[1]["t_start"], 3.9)  # departure event
        self.assertEqual(segments[1]["basis"], "still_mid")

    def test_trailing_animation_appends_screen(self):
        payload = self.mod.build_segments(
            {
                "duration_s": 6.0,
                "events": [ev(3.8, 3.9), ev(4.1, 4.2), ev(4.4, 4.5)],
                "stills": [still(0.1, 1.9)],
            },
            **self.kwargs,
        )
        segments = payload["segments"]
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[1]["t_start"], 3.8)  # event-anchored boundary
        self.assertEqual(segments[1]["t_end"], 6.0)
        self.assertEqual(segments[1]["grab_at"], 4.5)

    def test_no_stills_events_anchor_screens(self):
        payload = self.mod.build_segments(
            {
                "duration_s": 7.0,
                "events": [ev(1.0, 1.1), ev(3.5, 3.6), ev(6.0, 6.1)],
                "stills": [],
            },
            **self.kwargs,
        )
        self.assertEqual(payload["mode"], "event")
        segments = payload["segments"]
        self.assertEqual(len(segments), 3)
        self.assertEqual([s["grab_at"] for s in segments], [1.1, 3.6, 6.1])
        self.assertTrue(all(s["basis"] == "event_settle" for s in segments))

    def test_uniform_fallback_without_anchors(self):
        payload = self.mod.build_segments(
            {"duration_s": 6.0, "events": [], "stills": []}, **self.kwargs
        )
        self.assertEqual(payload["mode"], "uniform")
        self.assertIsNotNone(payload["fallback_reason"])
        segments = payload["segments"]
        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[0]["t_start"], 0.0)
        self.assertEqual(segments[-1]["t_end"], 6.0)
        self.assertTrue(all(s["basis"] == "sample" for s in segments))

    def test_max_screens_falls_back_to_uniform(self):
        payload = self.mod.build_segments(
            {
                "duration_s": 10.0,
                "events": [],
                "stills": [still(k, k + 0.5) for k in range(10)],
            },
            **{**self.kwargs, "max_screens": 3},
        )
        self.assertEqual(payload["mode"], "uniform")
        self.assertIn("max-screens", payload["fallback_reason"])
        self.assertLessEqual(len(payload["segments"]), 3)

    def test_single_still_single_screen(self):
        payload = self.mod.build_segments(
            {"duration_s": 6.0, "events": [], "stills": [still(0.1, 5.9)]}, **self.kwargs
        )
        segments = payload["segments"]
        self.assertEqual(len(segments), 1)
        self.assertEqual((segments[0]["t_start"], segments[0]["t_end"]), (0.0, 6.0))

    def test_missing_duration_raises(self):
        with self.assertRaises(ValueError):
            self.mod.build_segments({"events": [], "stills": []}, **self.kwargs)

    def test_segments_never_overlap(self):
        payload = self.mod.build_segments(
            {
                "duration_s": 12.0,
                "events": [ev(2.9, 3.0), ev(6.9, 7.0), ev(2.0, 2.1)],
                "stills": [still(0.1, 2.8), still(3.2, 6.8), still(7.2, 11.8)],
            },
            **self.kwargs,
        )
        segments = payload["segments"]
        for prev, nxt in zip(segments, segments[1:]):
            self.assertLessEqual(prev["t_start"], prev["t_end"])
            self.assertLessEqual(prev["t_end"], nxt["t_start"])


if __name__ == "__main__":
    unittest.main()
