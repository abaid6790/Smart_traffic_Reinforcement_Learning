"""Runs one complete episode: a simulator, a controller and the metrics.

This is the single place where "controller + simulator + measurements" are put
together, so a fixed-time run and an RL run are executed and measured in
exactly the same way.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from config.settings import Settings
from controllers.base import Controller
from evaluation.metrics import EpisodeMetrics, MetricsCollector, TimeSeries
from simulation.simulator import Simulator


@dataclass
class EpisodeResult:
    """Everything produced by one run."""

    metrics: EpisodeMetrics
    series: TimeSeries
    simulator: Simulator  # final state, for inspection and tests


def run_episode(
    settings: Settings,
    controller: Controller,
    seed: int | None = None,
    on_step: Callable[[Simulator], None] | None = None,
    sample_interval: float = 5.0,
) -> EpisodeResult:
    """Simulate one full run with ``controller`` in charge of the light.

    ``seed`` overrides ``settings.traffic.seed``.  The traffic depends only on the
    seed and scenario, so two controllers run with the same seed face exactly the
    same vehicles.

    ``on_step`` (optional) is called once at the start and again after every step,
    for example to print progress.
    """
    sim = Simulator(settings)
    if seed is not None:
        sim.reset(seed=seed)
    controller.reset()
    collector = MetricsCollector(sample_interval)
    if on_step is not None:
        on_step(sim)
    while not sim.finished:
        controller.act(sim)
        sim.step()
        collector.record(sim)
        if on_step is not None:
            on_step(sim)
    return EpisodeResult(collector.result(sim, controller.name), collector.series, sim)
