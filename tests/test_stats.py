import math
import random
import unittest

from evaluation.stats import paired_comparison, summarize, t_critical


class SummaryTests(unittest.TestCase):
    def test_mean_std_and_interval_match_a_hand_calculation(self):
        s = summarize([1, 2, 3, 4, 5])
        self.assertEqual(s.n, 5)
        self.assertAlmostEqual(s.mean, 3.0)
        self.assertAlmostEqual(s.std, math.sqrt(2.5))
        half = 2.776 * math.sqrt(2.5) / math.sqrt(5)  # t(4) = 2.776
        self.assertAlmostEqual(s.ci_low, 3 - half)
        self.assertAlmostEqual(s.ci_high, 3 + half)
        self.assertAlmostEqual(s.half_width, half)

    def test_missing_values_are_left_out_not_counted_as_zero(self):
        s = summarize([2, None, 4, None, 6])
        self.assertEqual((s.n, s.mean), (3, 4.0))

    def test_too_little_data_gives_no_interval(self):
        none = summarize([])
        self.assertEqual((none.n, none.mean, none.ci_low, none.half_width), (0, None, None, None))
        self.assertIsNone(summarize([None, None]).mean)
        one = summarize([7.5])
        self.assertEqual((one.n, one.mean, one.std, one.ci_low), (1, 7.5, None, None))

    def test_identical_values_have_zero_width(self):
        s = summarize([3.0] * 6)
        self.assertEqual((s.std, s.ci_low, s.ci_high), (0.0, 3.0, 3.0))

    def test_t_values(self):
        self.assertEqual(t_critical(1), 12.706)
        self.assertEqual(t_critical(19), 2.093)
        self.assertEqual(t_critical(35), 2.042)   # between rows: the wider (safer) value
        self.assertEqual(t_critical(45), 2.021)
        self.assertEqual(t_critical(100), 2.0)
        self.assertEqual(t_critical(10_000), 1.96)
        for bad in (0, -1):
            with self.assertRaises(ValueError):
                t_critical(bad)
        values = [t_critical(n) for n in range(1, 200)]
        self.assertEqual(values, sorted(values, reverse=True))  # never increases with more data

    def test_the_interval_covers_the_true_mean_about_95_percent_of_the_time(self):
        rng = random.Random(1)
        for n in (5, 10, 20):
            hits = 0
            trials = 2000
            for _ in range(trials):
                s = summarize([rng.gauss(10, 3) for _ in range(n)])
                hits += s.ci_low <= 10 <= s.ci_high
            self.assertTrue(0.93 <= hits / trials <= 0.97, (n, hits / trials))


class PairedTests(unittest.TestCase):
    def test_a_consistent_improvement_is_better(self):
        base = [10, 12, 11, 13, 12, 11]
        cand = [8, 10, 9.5, 11, 10, 9]
        p = paired_comparison(base, cand, lower_is_better=True)
        self.assertEqual(p.verdict, "better")
        self.assertEqual((p.candidate_better, p.candidate_worse, p.ties, p.n), (6, 0, 0, 6))
        self.assertLess(p.differences.mean, 0)

    def test_direction_depends_on_the_metric(self):
        base, cand = [100, 110, 105, 108], [120, 128, 126, 131]
        self.assertEqual(paired_comparison(base, cand, lower_is_better=False).verdict, "better")
        self.assertEqual(paired_comparison(base, cand, lower_is_better=True).verdict, "worse")

    def test_noise_is_no_clear_difference(self):
        base = [10, 12, 11, 13, 12, 11]
        cand = [10.5, 11.5, 11.2, 12.8, 12.4, 10.6]  # sometimes higher, sometimes lower
        p = paired_comparison(base, cand, lower_is_better=True)
        self.assertEqual(p.verdict, "no clear difference")
        self.assertGreater(p.candidate_better, 0)
        self.assertGreater(p.candidate_worse, 0)

    def test_ties_and_missing_values(self):
        p = paired_comparison([1, 2, None, 4], [1, 1, 5, None], lower_is_better=True)
        self.assertEqual((p.n, p.candidate_better, p.candidate_worse, p.ties), (2, 1, 0, 1))
        self.assertEqual(p.verdict, "no clear difference")  # two runs can never be conclusive here

    def test_pairing_matters(self):
        """Large run-to-run differences cancel when the same traffic is compared."""
        base = [5, 50, 20, 80, 35]
        cand = [4.5, 49.0, 19.2, 79.0, 34.3]
        self.assertEqual(paired_comparison(base, cand, True).verdict, "better")
        self.assertEqual(summarize(base).ci_low < summarize(cand).ci_high, True)  # unpaired overlaps

    def test_mismatched_lengths_are_refused(self):
        with self.assertRaises(ValueError):
            paired_comparison([1, 2], [1], True)

    def test_a_single_run_is_never_conclusive(self):
        self.assertEqual(paired_comparison([10], [1], True).verdict, "no clear difference")


if __name__ == "__main__":
    unittest.main()
