"""Finds good green times for the fixed-time controller.

The default 30 s / 30 s is only an example; for the simulated traffic shorter greens often
work much better.  To compare a learning agent fairly, it should be compared with a
fixed-time controller that has been *tuned* too.  This module tries many NS/EW green-time
pairs and keeps the one with the lowest average waiting time of all vehicles.

It tunes on the validation seeds (``evaluation.seeds.validation_seed``), never on the
evaluation seeds used to compare controllers, so the tuned controller gets no peek at the
test traffic.  The settings' own green times are always among the candidates, so tuning
can never end up *worse* than the starting point on the tuning seeds.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from config.settings import Settings
from controllers.fixed_controller import FixedTimeController
from evaluation.seeds import validation_seed
from simulation.runner import run_episode

DEFAULT_CANDIDATES: tuple[float, ...] = (10, 15, 20, 25, 30, 40, 50)


@dataclass(frozen=True)
class TuningResult:
    scenario: str
    ns_green: float
    ew_green: float
    score: float  # average waiting time (all vehicles) on the tuning seeds, seconds
    start_ns_green: float
    start_ew_green: float
    start_score: float
    runs: int
    tried: tuple[tuple[float, float, float], ...] = field(default_factory=tuple)  # (ns, ew, score)


def tune_fixed_time(
    settings: Settings,
    scenario: str | None = None,
    runs: int = 4,
    candidates: Sequence[float] = DEFAULT_CANDIDATES,
    on_progress: Callable[[int, int], None] | None = None,
) -> TuningResult:
    """Search NS and EW green times for ``scenario`` (default: the settings' scenario)."""
    if runs < 1:
        raise ValueError("runs must be at least 1")
    base = settings.validate()
    if scenario is not None:
        base = base.with_changes("traffic", scenario=scenario)
    lights = base.lights
    values = sorted({float(v) for v in candidates if lights.min_green <= v <= lights.max_green})
    start = (base.fixed.ns_green, base.fixed.ew_green)
    pairs = [(a, b) for a in values for b in values]
    if start not in pairs:
        pairs.insert(0, start)

    seed0 = base.traffic.seed
    scores: dict[tuple[float, float], float] = {}
    for index, (ns, ew) in enumerate(pairs):
        trial = base.with_changes("fixed", ns_green=ns, ew_green=ew)
        waits = []
        for run in range(runs):
            metrics = run_episode(trial, FixedTimeController(trial), seed=validation_seed(seed0, run)).metrics
            if metrics.average_waiting_time_all is not None:
                waits.append(metrics.average_waiting_time_all)
        scores[(ns, ew)] = sum(waits) / len(waits) if waits else float("inf")
        if on_progress is not None:
            on_progress(index + 1, len(pairs))

    # lowest score wins; on a tie keep the starting pair, then the shorter cycle
    best = min(scores, key=lambda p: (scores[p], p != start, p[0] + p[1], p))
    return TuningResult(
        scenario=base.traffic.scenario,
        ns_green=best[0], ew_green=best[1], score=scores[best],
        start_ns_green=start[0], start_ew_green=start[1], start_score=scores[start],
        runs=runs,
        tried=tuple((a, b, scores[(a, b)]) for a, b in pairs),
    )
