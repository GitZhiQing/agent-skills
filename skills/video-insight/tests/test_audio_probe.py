import unittest

from test_common import load_module


ASTATS_SAMPLE = """[Parsed_astats_0 @ 0x1fe1d0c5f00] Channel layout: stereo
[Parsed_astats_0 @ 0x1fe1d0c5f00] Flat factor: 0.000000
[Parsed_astats_0 @ 0x1fe1d0c5f00] RMS level dB: -18.960000
[Parsed_astats_0 @ 0x1fe1d0c5f00] Channel layout: stereo
[Parsed_astats_0 @ 0x1fe1d0c5f00] Flat factor: 0.000000
[Parsed_astats_0 @ 0x1fe1d0c5f00] RMS level dB: -19.100000
[Parsed_astats_0 @ 0x1fe1d0c5f00] Overall
[Parsed_astats_0 @ 0x1fe1d0c5f00] Flat factor: 0.000000
[Parsed_astats_0 @ 0x1fe1d0c5f00] Peak level dB: -1.428177
[Parsed_astats_0 @ 0x1fe1d0c5f00] RMS level dB: -19.077420
[Parsed_astats_0 @ 0x1fe1d0c5f00] Noise floor dB: -53.109982
"""


class TestAstatsOverall(unittest.TestCase):
    def setUp(self):
        self.mod = load_module("audio_probe")

    def test_overall_section_only(self):
        stats = self.mod._astats_overall(
            ASTATS_SAMPLE, ("RMS level dB", "Peak level dB", "Noise floor dB")
        )
        self.assertAlmostEqual(stats["RMS level dB"], -19.07742)
        self.assertAlmostEqual(stats["Peak level dB"], -1.428177)
        self.assertAlmostEqual(stats["Noise floor dB"], -53.109982)

    def test_no_overall_returns_empty(self):
        stats = self.mod._astats_overall("no astats here", ("RMS level dB",))
        self.assertEqual(stats, {})

    def test_minus_inf(self):
        sample = "Overall\n[Parsed_astats_0 @ x] RMS level dB: -inf\n"
        stats = self.mod._astats_overall(sample, ("RMS level dB",))
        self.assertEqual(stats["RMS level dB"], float("-inf"))


if __name__ == "__main__":
    unittest.main()
