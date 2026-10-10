"""Fair comparison of controllers on identical traffic.

For each scenario the experiment runs every controller on the *same* list of traffic seeds
(``evaluation.seeds.evaluation_seed``): same arrival pattern, same duration, same starting
state.  The three controllers are

* ``fixed``        the fixed-time controller with the green times in the settings (default 30 s),
* ``fixed_tuned``  the fixed-time controller with green times tuned for that scenario on
                   separate seeds (``controllers.tuning``) - a stronger baseline,
* ``rl``           the trained Q-Learning agent, with exploration and learning switched off.

Results are summarised with 95 % confidence intervals and compared seed by seed
(``evaluation.stats``).  Nothing here is estimated: every number comes from a real run.

*Total reward* is the Phase 5 reward formula applied to every controller in the same way,
on a common grid of ``rl.decision_interval`` seconds, so controllers that do not take
decisions (the fixed-time ones) are scored on exactly the same scale.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from agents.q_learning import QLearningAgent
from config.settings import PROJECT_VERSION, SCENARIO_NAMES, RLConfig, Settings
from controllers.base import Controller
from controllers.fixed_controller import FixedTimeController
from controllers.rl_controller import QLearningController
from controllers.tuning import TuningResult, tune_fixed_time
from evaluation.metrics import HIGHER_IS_BETTER, LOWER_IS_BETTER, EpisodeMetrics, improvement_percent
from evaluation.seeds import evaluation_seed
from evaluation.stats import PairedComparison, Summary, paired_comparison, summarize
from simulation.runner import run_episode
from simulation.simulator import Simulator

FIXED, TUNED, RL = "fixed", "fixed_tuned", "rl"
LABELS = {FIXED: "Fixed-time (default)", TUNED: "Fixed-time (tuned)", RL: "Q-Learning"}
MAX_RUNS = 200
_EPS = 1e-9


@dataclass(frozen=True)
class MetricInfo:
    name: str
    label: str
    unit: str
    lower_is_better: bool
    digits: int = 1


#: Every metric reported, in display order.
METRICS: tuple[MetricInfo, ...] = (
    MetricInfo("average_waiting_time_all", "Average waiting time (all vehicles)", "s", True),
    MetricInfo("average_waiting_time", "Average waiting time (served vehicles)", "s", True),
    MetricInfo("max_waiting_time", "Maximum waiting time", "s", True),
    MetricInfo("average_queue_length", "Average queue length", "vehicles", True),
    MetricInfo("max_queue_length", "Maximum queue length", "vehicles", True, 1),
    MetricInfo("vehicles_served", "Vehicles served", "vehicles", False, 1),
    MetricInfo("throughput_per_minute", "Throughput", "vehicles/min", False),
    MetricInfo("average_travel_time", "Average travel time", "s", True),
    MetricInfo("average_stops", "Average stops per vehicle", "stops", True, 2),
    MetricInfo("light_switches", "Light switches", "switches", True, 1),
    MetricInfo("total_reward", "Total reward", "points", False),
)
METRIC_BY_NAME = {m.name: m for m in METRICS}
HEADLINE_METRIC = "average_waiting_time_all"
assert set(LOWER_IS_BETTER + HIGHER_IS_BETTER) <= set(METRIC_BY_NAME)


class RewardMeter:
    """Scores a run with the environment's reward formula on a fixed time grid.

    Pass it as ``on_step`` to ``run_episode``.  Every ``rl.decision_interval`` seconds (and at
    the end of the run) it adds ``(waiting before - waiting now) - switch_penalty x switches
    - queue_penalty x vehicles waiting beyond queue_limit`` to ``total``.
    """

    def __init__(self, rl: RLConfig) -> None:
        self.rl = rl
        self.total = 0.0
        self._waiting: int | None = None
        self._switches = 0
        self._next = rl.decision_interval

    def __call__(self, sim: Simulator) -> None:
        if self._waiting is None:  # the call before the first step
            self._waiting = sum(sim.queue_lengths().values())
            self._switches = sim.light.switch_count
            return
        if sim.time < self._next - _EPS and not sim.finished:
            return
        waiting = sum(sim.queue_lengths().values())
        switches = sim.light.switch_count
        rl = self.rl
        self.total += ((self._waiting - waiting)
                       - rl.switch_penalty * (switches - self._switches)
                       - rl.queue_penalty * max(0, waiting - rl.queue_limit))
        self._waiting, self._switches = waiting, switches
        while self._next <= sim.time + _EPS:
            self._next += rl.decision_interval


@dataclass(frozen=True)
class RunRecord:
    """One controller, one scenario, one seed."""

    controller: str
    scenario: str
    run: int
    seed: int
    metrics: EpisodeMetrics
    total_reward: float

    def value(self, metric: str) -> float | None:
        if metric == "total_reward":
            return self.total_reward
        value = getattr(self.metrics, metric)
        return None if value is None else float(value)


@dataclass(frozen=True)
class Comparison:
    """One controller against another on one metric."""

    metric: str
    base: str
    candidate: str
    base_mean: float | None
    candidate_mean: float | None
    improvement_percent: float | None  # of the means; None for total reward (can be negative)
    paired: PairedComparison


@dataclass
class AveragedSeries:
    """A time series averaged over the runs of one controller (for the over-time graphs)."""

    times: list[float] = field(default_factory=list)
    total_queue: list[float] = field(default_factory=list)
    vehicles_in_system: list[float] = field(default_factory=list)
    average_wait_so_far: list[float | None] = field(default_factory=list)  # served vehicles


@dataclass
class ScenarioResult:
    scenario: str
    seeds: list[int]
    records: dict[str, list[RunRecord]] = field(default_factory=dict)
    tuning: TuningResult | None = None
    series: dict[str, AveragedSeries] = field(default_factory=dict)

    @property
    def controllers(self) -> list[str]:
        return [key for key in (FIXED, TUNED, RL) if self.records.get(key)]

    @property
    def runs(self) -> int:
        return min((len(v) for v in self.records.values()), default=0)

    def values(self, controller: str, metric: str) -> list[float | None]:
        return [r.value(metric) for r in self.records.get(controller, [])]

    def summary(self, controller: str, metric: str) -> Summary:
        return summarize(self.values(controller, metric))

    def compare(self, candidate: str, base: str, metric: str) -> Comparison:
        info = METRIC_BY_NAME[metric]
        paired = paired_comparison(self.values(base, metric), self.values(candidate, metric),
                                   info.lower_is_better)
        base_mean = self.summary(base, metric).mean
        cand_mean = self.summary(candidate, metric).mean
        percent = None if metric == "total_reward" else improvement_percent(
            base_mean, cand_mean, info.lower_is_better)
        return Comparison(metric, base, candidate, base_mean, cand_mean, percent, paired)

    def traffic_was_identical(self) -> bool:
        """True if every controller saw the same number of arriving vehicles in every run."""
        by_run: dict[int, set[int]] = {}
        for records in self.records.values():
            for r in records:
                by_run.setdefault(r.run, set()).add(r.metrics.vehicles_arrived)
        return all(len(counts) == 1 for counts in by_run.values())

    def safety_violations(self) -> int:
        return sum(r.metrics.safety_violations for rs in self.records.values() for r in rs)


@dataclass
class ExperimentResult:
    created: str
    settings: dict[str, Any]
    runs: int
    base_seed: int
    scenarios: list[ScenarioResult] = field(default_factory=list)
    model: dict[str, Any] | None = None
    seconds: float = 0.0
    stopped_early: bool = False
    version: str = PROJECT_VERSION

    def scenario(self, name: str) -> ScenarioResult:
        for result in self.scenarios:
            if result.scenario == name:
                return result
        raise KeyError(name)


def _average_series(series_list: list) -> AveragedSeries:
    averaged = AveragedSeries()
    if not series_list:
        return averaged
    length = min(len(s.times) for s in series_list)
    n = len(series_list)
    for i in range(length):
        averaged.times.append(series_list[0].times[i])
        averaged.total_queue.append(sum(s.total_queue[i] for s in series_list) / n)
        averaged.vehicles_in_system.append(sum(s.vehicles_in_system[i] for s in series_list) / n)
        waits = [s.average_wait_so_far[i] for s in series_list if s.average_wait_so_far[i] is not None]
        averaged.average_wait_so_far.append(sum(waits) / len(waits) if waits else None)
    return averaged


def run_experiment(
    settings: Settings,
    scenarios: list[str] | None = None,
    runs: int = 10,
    agent: QLearningAgent | None = None,
    tune: bool = True,
    tune_runs: int = 4,
    on_progress: Callable[[int, int, str], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> ExperimentResult:
    """Run the comparison.  ``agent=None`` leaves the Q-Learning controller out and
    ``tune=False`` leaves the tuned fixed-time controller out."""
    settings = settings.validate()
    names = list(scenarios) if scenarios else [settings.traffic.scenario]
    unknown = [n for n in names if n not in SCENARIO_NAMES]
    if unknown:
        raise ValueError(f"Unknown scenario(s): {', '.join(unknown)} (valid: {', '.join(SCENARIO_NAMES)})")
    if not isinstance(runs, int) or isinstance(runs, bool) or not 1 <= runs <= MAX_RUNS:
        raise ValueError(f"runs must be a whole number from 1 to {MAX_RUNS}")

    started = time.perf_counter()
    base_seed = settings.traffic.seed
    result = ExperimentResult(
        created=datetime.now().astimezone().isoformat(timespec="seconds"),
        settings=settings.to_dict(), runs=runs, base_seed=base_seed,
        model=_model_info(agent),
    )
    total = len(names) * runs * (1 + int(tune) + int(agent is not None))
    done = 0

    for name in names:
        scenario_settings = settings.with_changes("traffic", scenario=name)
        seeds = [evaluation_seed(base_seed, k) for k in range(runs)]
        scenario = ScenarioResult(name, seeds)
        result.scenarios.append(scenario)

        controllers: list[tuple[str, Settings, Controller]] = [
            (FIXED, scenario_settings, FixedTimeController(scenario_settings))]
        if tune:
            if on_progress:
                on_progress(done, total, f"{name}: tuning the fixed-time controller")
            scenario.tuning = tune_fixed_time(scenario_settings, runs=tune_runs)
            tuned = scenario_settings.with_changes(
                "fixed", ns_green=scenario.tuning.ns_green, ew_green=scenario.tuning.ew_green)
            controllers.append((TUNED, tuned, FixedTimeController(tuned)))
        if agent is not None:
            controllers.append((RL, scenario_settings, QLearningController(agent)))

        collected: dict[str, list] = {key: [] for key, _, _ in controllers}
        for key, run_settings, controller in controllers:
            scenario.records[key] = []
            for k, seed in enumerate(seeds):
                if should_stop is not None and should_stop():
                    result.stopped_early = True
                    break
                meter = RewardMeter(run_settings.rl)
                episode = run_episode(run_settings, controller, seed=seed, on_step=meter)
                scenario.records[key].append(
                    RunRecord(key, name, k, seed, episode.metrics, meter.total))
                collected[key].append(episode.series)
                done += 1
                if on_progress:
                    on_progress(done, total, f"{name}: {LABELS[key]} run {k + 1}/{runs}")
            if result.stopped_early:
                break
        if result.stopped_early:
            # A fair comparison needs every controller to have driven the same seeds, so
            # keep only the runs that all of them finished (a stop can arrive half way).
            common = min(len(runs_done) for runs_done in collected.values())
            for key in collected:
                collected[key] = collected[key][:common]
                scenario.records[key] = scenario.records.get(key, [])[:common]
            scenario.seeds = scenario.seeds[:common]
            if common == 0:
                result.scenarios.remove(scenario)
        scenario.series = {key: _average_series(s) for key, s in collected.items() if s}
        if result.stopped_early:
            break
    result.seconds = time.perf_counter() - started
    return result


def _model_info(agent: QLearningAgent | None) -> dict[str, Any] | None:
    if agent is None:
        return None
    training = agent.info.get("training", {}) if agent.info else {}
    return {
        "episodes_trained": agent.episodes_trained,
        "trained_on": training.get("scenarios"),
        "base_seed": training.get("base_seed"),
        "best_episode": training.get("best_episode"),
        "saved_at": agent.info.get("saved_at") if agent.info else None,
    }
