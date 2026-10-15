import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from test_common import load_module


class TestParseRange(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("grab_frames")

    def test_plain(self):
        self.assertEqual(self.mod.parse_range("4.0:5.3"), (4.0, 5.3))

    def test_bad_shape_raises(self):
        for spec in ("4.0", "4.0:5.3:6", "4-5", ""):
            with self.assertRaises(ValueError):
                self.mod.parse_range(spec)


class TestExpandRange(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("grab_frames")

    def test_even_step_inclusive_end(self):
        self.assertEqual(self.mod.expand_range(4.0, 5.5, 0.5), [4.0, 4.5, 5.0, 5.5])

    def test_end_not_on_step_grid(self):
        self.assertEqual(self.mod.expand_range(4.0, 5.3, 2.0), [4.0])

    def test_single_point_window(self):
        self.assertEqual(self.mod.expand_range(3.2, 3.2, 0.5), [3.2])

    def test_float_drift_is_rounded(self):
        times = self.mod.expand_range(0.0, 1.0, 0.1)
        self.assertEqual(times[-1], 1.0)
        self.assertTrue(all(round(t, 3) == t for t in times))

    def test_non_positive_step_raises(self):
        with self.assertRaises(ValueError):
            self.mod.expand_range(0.0, 1.0, 0.0)

    def test_end_before_start_raises(self):
        with self.assertRaises(ValueError):
            self.mod.expand_range(5.0, 4.0, 0.5)


class TestGrabRetry(unittest.TestCase):
    """Hot-fix coverage: -strict unofficial + last-frame fallback retry."""

    def setUp(self):
        self.mod = load_module("grab_frames")
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "frame.jpg"

    def test_strict_unofficial_in_both_branches(self):
        cmds: list[list[str]] = []

        def fake_run(cmd):
            cmds.append(cmd)
            self.target.write_bytes(b"jpg")

        with mock.patch.object(self.mod, "run", side_effect=fake_run):
            self.mod.grab(Path("in.mp4"), 1.0, self.target, crop=None, zoom=4, flags="neighbor")
            self.mod.grab(Path("in.mp4"), 1.0, self.target,
                          crop=(720, 80, 0, 930), zoom=4, flags="neighbor")
        for cmd in cmds:
            self.assertIn("-strict", cmd)
            self.assertIn("unofficial", cmd)

    def test_retry_records_t_effective(self):
        def fake_run(cmd):
            if "10.000" in cmd:  # first attempt at t=10.0 fails
                raise RuntimeError("no frame")
            self.target.write_bytes(b"jpg")  # retry at t-0.2 produces the frame

        with mock.patch.object(self.mod, "run", side_effect=fake_run):
            record = self.mod.grab(Path("in.mp4"), 10.0, self.target,
                                   crop=None, zoom=4, flags="neighbor")
        self.assertEqual(record["t"], 10.0)
        self.assertEqual(record["t_effective"], 9.8)

    def test_both_attempts_fail_raises(self):
        with mock.patch.object(self.mod, "run", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                self.mod.grab(Path("in.mp4"), 10.0, self.target,
                              crop=None, zoom=4, flags="neighbor")


class TestCliMutualExclusion(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("grab_frames")
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.input = Path(self.tmp.name) / "in.mp4"
        self.input.write_bytes(b"0")

    def test_at_and_range_together_exit_2(self):
        with self.assertRaises(SystemExit) as ctx:
            self.mod.main([str(self.input), "--at", "1.0", "--range", "0:2.0"])
        self.assertEqual(ctx.exception.code, 2)

    def test_neither_at_nor_range_exit_2(self):
        with self.assertRaises(SystemExit) as ctx:
            self.mod.main([str(self.input)])
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
