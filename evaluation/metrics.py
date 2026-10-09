"""Performance metrics for one simulation run (an "episode").

Every formula is documented in ``docs/METRICS.md``.  In short, using these words:

* *served* (or completed) vehicles have driven all the way out of the simulation;
* *arrived* vehicles include served ones plus those still on the road or waiting
  to enter when the run ends (*unserved*).

======================  =====================================================
Metric                  Definition
======================  =====================================================
average_waiting_time    total waiting time of served vehicles / served vehicles
average_waiting_time_all  the same, over **all arrived** vehicles
max_waiting_time        longest waiting time of any arrived vehicle
average_queue_length    time-average of the total number of standing vehicles
max_queue_length        largest total queue seen at any time step
vehicles_served         number of served vehicles
throughput_per_minute   vehicles served / simulated minutes
average_travel_time     mean time from arrival to leaving, served vehicles
average_stops           mean number of stops per served vehicle
======================  =====================================================

Why two waiting-time averages?  The first is the standard definition, but it
ignores vehicles that are still stuck in a queue when the run ends, so a controller
that leaves many cars waiting could look better than it is.  The "all vehicles"
version and the ``vehicles_unserved`` count make that visible.

An average that cannot be computed (for example, no vehicle finished) is ``None``,
never ``0``, so missing data can never look like perfect performance.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

from environment.enums import ALL_DIRECTIONS, Direction

if TYPE_CHECKING:
    from simulation.simulator import Simulator

# Metrics where a smaller value is better, and where a larger value is better.
# Used to turn two sets of results into "percent improvement" numbers.
LOWER_IS_BETTER: tuple[str, ...] = (
    "average_waiting_time",
    "average_waiting_time_all",
    "max_waiting_time",
    "average_queue_length",
    "max_queue_length",
    "average_travel_time",
    "average_stops",
)
HIGHER_IS_BETTER: tuple[str, ...] = ("vehicles_served", "throughput_per_minute")


@dataclass(frozen=True)
class EpisodeMetrics:
    """The results of one run.  ``None`` means "cannot be computed"."""

    controller: str
    scenario: str
    seed: int
    duration: float  # simulated seconds
    vehicles_arrived: int
    vehicles_served: int
    vehicles_unserved: int
    average_waiting_time: float | None
    average_waiting_time_all: float | None
    max_waiting_time: float | None
    average_queue_length: float | None
    max_queue_length: int
    average_queue_by_road: dict[str, float]
    average_travel_time: float | None
    average_stops: float | None
    total_stops: int
    throughput_per_minute: float
    light_switches: int
    safety_violations: int

    def to_dict(self) -> dict[str, Any]:
        """Plain dictionary, ready for CSV or JSON export."""
        return asdict(self)


@dataclass
class TimeSeries:
    """Values sampled during a run, for "over time" graphs.

    ``average_wait_so_far`` is the average waiting time of the vehicles that have
    been served up to that moment (``None`` until the first vehicle is served).
    """

    times: list[float] = field(default_factory=list)
    total_queue: list[int] = field(default_factory=list)
    vehicles_in_system: list[int] = field(default_factory=list)
    average_wait_so_far: list[float | None] = field(default_factory=list)


def _mean(values: Iterable[float]) -> float | None:
    items = list(values)
    return sum(items) / len(items) if items else None


class MetricsCollector:
    """Watches a simulation step by step and produces :class:`EpisodeMetrics`.

    Call :meth:`record` once after every ``Simulator.step()``, then
    :meth:`result` at the end.
    """

    def __init__(self, sample_interval: float = 5.0) -> None:
        if not sample_interval > 0:
            raise ValueError("sample_interval must be greater than 0.")
        self.sample_interval = sample_interval
        self.reset()

    def reset(self) -> None:
        """Forget everything and start a new run."""
        self.steps = 0
        self.series = TimeSeries()
        self._queue_sum = 0
        self._queue_sum_by_road = {d: 0 for d in ALL_DIRECTIONS}
        self._max_queue = 0
        self._completed_seen = 0
        self._completed_wait_sum = 0.0
        self._next_sample = 0.0

    def record(self, sim: Simulator) -> None:
        """Record the state of ``sim`` after a step."""
        completed = sim.completed
        for vehicle in completed[self._completed_seen:]:
            self._completed_wait_sum += vehicle.waiting_time
        self._completed_seen = len(completed)
        self.record_values(
            sim.time,
            sim.queue_lengths(),
            sim.vehicles_in_system(),
            self._completed_seen,
            self._completed_wait_sum,
        )

    def record_values(
        self,
        time: float,
        queues: Mapping[Direction, int],
        vehicles_in_system: int,
        completed_count: int = 0,
        completed_wait_sum: float = 0.0,
    ) -> None:
        """Record one time step from plain numbers (used by :meth:`record`)."""
        total = sum(queues[d] for d in ALL_DIRECTIONS)
        self.steps += 1
        self._queue_sum += total
        self._max_queue = max(self._max_queue, total)
        for direction in ALL_DIRECTIONS:
            self._queue_sum_by_road[direction] += queues[direction]

        if time >= self._next_sample:
            self.series.times.append(time)
            self.series.total_queue.append(total)
            self.series.vehicles_in_system.append(vehicles_in_system)
            self.series.average_wait_so_far.append(
                completed_wait_sum / completed_count if completed_count else None
            )
            while self._next_sample <= time:
                self._next_sample += self.sample_interval

    def result(self, sim: Simulator, controller_name: str) -> EpisodeMetrics:
        """Compute the final metrics for the run recorded so far."""
        served = sim.completed
        everyone = sim.all_vehicles()
        steps = self.steps
        minutes = sim.time / 60.0
        return EpisodeMetrics(
            controller=controller_name,
            scenario=sim.settings.traffic.scenario,
            seed=sim.generator.seed,
            duration=sim.time,
            vehicles_arrived=len(everyone),
            vehicles_served=len(served),
            vehicles_unserved=len(everyone) - len(served),
            average_waiting_time=_mean(v.waiting_time for v in served),
            average_waiting_time_all=_mean(v.waiting_time for v in everyone),
            max_waiting_time=max((v.waiting_time for v in everyone), default=None),
            average_queue_length=self._queue_sum / steps if steps else None,
            max_queue_length=self._max_queue,
            average_queue_by_road=(
                {d.value: self._queue_sum_by_road[d] / steps for d in ALL_DIRECTIONS}
                if steps
                else {}
            ),
            average_travel_time=_mean(v.travel_time for v in served),
            average_stops=_mean(v.stops for v in served),
            total_stops=sum(v.stops for v in everyone),
            throughput_per_minute=len(served) / minutes if minutes > 0 else 0.0,
            light_switches=sim.light.switch_count,
            safety_violations=sim.safety_violations,
        )


# --------------------------------------------------------------------------
# Comparing two sets of results
# --------------------------------------------------------------------------


def improvement_percent(
    baseline: float | None, candidate: float | None, lower_is_better: bool = True
) -> float | None:
    """Percent by which ``candidate`` beats ``baseline`` (negative = worse).

    * lower is better (waiting time, queues, ...):
      ``(baseline - candidate) / baseline * 100``
    * higher is better (vehicles served, throughput):
      ``(candidate - baseline) / baseline * 100``

    Returns ``None`` when it cannot be computed (a missing value, or a baseline
    of zero).  Two equal values give ``0.0``.
    """
    if baseline is None or candidate is None:
        return None
    if baseline == candidate:
        return 0.0
    if baseline == 0:
        return None
    difference = baseline - candidate if lower_is_better else candidate - baseline
    return difference / baseline * 100.0


def compare_metrics(
    baseline: EpisodeMetrics, candidate: EpisodeMetrics
) -> dict[str, float | None]:
    """Percent improvement of ``candidate`` over ``baseline`` for every metric.

    Positive means the candidate (for example the RL agent) did better.
    """
    changes: dict[str, float | None] = {}
    for name in LOWER_IS_BETTER:
        changes[name] = improvement_percent(
            getattr(baseline, name), getattr(candidate, name), lower_is_better=True
        )
    for name in HIGHER_IS_BETTER:
        changes[name] = improvement_percent(
            getattr(baseline, name), getattr(candidate, name), lower_is_better=False
        )
    return changes
