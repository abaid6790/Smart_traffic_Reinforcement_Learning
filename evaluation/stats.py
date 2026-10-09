"""Small statistics helpers (standard library only).

Used by the experiments to say how sure we can be about a difference, not just what the
averages are.  Everything here is documented in ``docs/EXPERIMENTS.md``.

* ``summarize`` gives the mean, standard deviation and a 95 % confidence interval of a list
  of run results (Student's t distribution, because there are only 10-20 runs).
* ``paired_comparison`` compares two controllers run on the *same* traffic seeds: it works on
  the difference seed by seed, which removes the luck of easy or hard traffic.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

# Two-sided 95 % critical values of Student's t distribution, by degrees of freedom.
_T_95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306,
    9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
    16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074,
    23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045,
    30: 2.042, 40: 2.021, 60: 2.000, 120: 1.980,
}


def t_critical(degrees_of_freedom: int) -> float:
    """Two-sided 95 % critical value of the t distribution (rounds *up* between table rows,
    which makes intervals slightly wider, never narrower)."""
    if degrees_of_freedom < 1:
        raise ValueError("degrees of freedom must be at least 1")
    if degrees_of_freedom in _T_95:
        return _T_95[degrees_of_freedom]
    if degrees_of_freedom < 40:
        return _T_95[30]
    if degrees_of_freedom < 60:
        return _T_95[40]
    if degrees_of_freedom < 120:
        return _T_95[60]
    return _T_95[120] if degrees_of_freedom < 1000 else 1.96


@dataclass(frozen=True)
class Summary:
    """Mean, spread and 95 % confidence interval of some values."""

    n: int
    mean: float | None
    std: float | None  # sample standard deviation (needs 2 values)
    ci_low: float | None  # 95 % confidence interval of the mean (needs 2 values)
    ci_high: float | None

    @property
    def half_width(self) -> float | None:
        return None if self.ci_low is None or self.mean is None else self.mean - self.ci_low


def summarize(values: Sequence[float | None]) -> Summary:
    """Summarise ``values``; missing values (``None``) are left out."""
    data = [float(v) for v in values if v is not None]
    n = len(data)
    if n == 0:
        return Summary(0, None, None, None, None)
    mean = math.fsum(data) / n
    if n == 1:
        return Summary(1, mean, None, None, None)
    std = math.sqrt(math.fsum((v - mean) ** 2 for v in data) / (n - 1))
    half = t_critical(n - 1) * std / math.sqrt(n)
    return Summary(n, mean, std, mean - half, mean + half)


@dataclass(frozen=True)
class PairedComparison:
    """Candidate minus base, run by run, on identical traffic."""

    n: int  # runs where both had a value
    differences: Summary  # of (candidate - base)
    candidate_better: int  # runs where the candidate had the better value
    candidate_worse: int
    ties: int
    verdict: str  # "better", "worse" or "no clear difference"


def paired_comparison(base: Sequence[float | None], candidate: Sequence[float | None],
                      lower_is_better: bool) -> PairedComparison:
    """Compare two controllers seed by seed.

    The verdict is "better" or "worse" only when the 95 % confidence interval of the
    mean difference lies completely on one side of zero; otherwise "no clear difference".
    """
    if len(base) != len(candidate):
        raise ValueError("Both controllers need the same number of runs.")
    pairs = [(b, c) for b, c in zip(base, candidate) if b is not None and c is not None]
    diffs = [c - b for b, c in pairs]
    summary = summarize(diffs)
    better = sum(1 for d in diffs if (d < 0 if lower_is_better else d > 0))
    worse = sum(1 for d in diffs if (d > 0 if lower_is_better else d < 0))
    verdict = "no clear difference"
    if summary.ci_low is not None and summary.ci_high is not None:
        if summary.ci_high < 0:
            verdict = "better" if lower_is_better else "worse"
        elif summary.ci_low > 0:
            verdict = "worse" if lower_is_better else "better"
    return PairedComparison(len(pairs), summary, better, worse, len(diffs) - better - worse,
                            verdict)
