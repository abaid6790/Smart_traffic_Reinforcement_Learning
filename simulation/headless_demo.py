"""A text-only demonstration of a full run (no window needed).

Run it with ``python main.py --demo``.  It runs one simulation with a controller in
charge of the light (the fixed-time controller by default), prints a progress table
and then the performance metrics.
"""

from __future__ import annotations

from collections.abc import Callable

from config.settings import Settings, get_scenario
from controllers.base import Controller
from controllers.fixed_controller import FixedTimeController
from environment.enums import ALL_DIRECTIONS
from evaluation.formatting import format_metrics
from simulation.runner import EpisodeResult, run_episode
from simulation.simulator import Simulator
from simulation.traffic_generator import resolve_rates

_EPS = 1e-9


def _row(sim: Simulator) -> str:
    queues = sim.queue_lengths()
    queue_text = " ".join(f"{queues[d]:>3}" for d in ALL_DIRECTIONS)
    return (
        f"{sim.time:>7.0f}s | {sim.light.phase.value} {sim.light.stage.value:<7} | "
        f"{queue_text} | {sim.vehicles_in_system():>9} | "
        f"{len(sim.completed):>6} | {sim.spawned:>7}"
    )


def run_demo(
    settings: Settings,
    controller: Controller | None = None,
    report_every: float = 30.0,
    out: Callable[[str], None] = print,
) -> EpisodeResult:
    """Run one full simulation, printing progress and metrics; return the result."""
    controller = controller or FixedTimeController(settings)
    traffic = settings.traffic
    profile = get_scenario(traffic.scenario)
    rates = resolve_rates(profile, traffic)

    out(f"Scenario   : {profile.name} - {profile.description}")
    out(f"Seed       : {traffic.seed}    Duration: {settings.simulation.duration:g} s")
    arrivals = ", ".join(f"{d.label} {rates[d] * 60:.1f}/min" for d in ALL_DIRECTIONS)
    out(f"Arrivals   : {arrivals}")
    out(f"Controller : {controller.describe()}")
    out("")
    out("    Time | Light        |   N   S   E   W | In system |   Done | Arrived")
    out("-" * 72)

    progress = {"next": 0.0, "printed": -1.0}

    def show_progress(sim: Simulator) -> None:
        if sim.time >= progress["next"] - _EPS:
            out(_row(sim))
            progress["printed"] = sim.time
            progress["next"] += report_every

    result = run_episode(settings, controller, on_step=show_progress)
    if progress["printed"] < result.simulator.time - _EPS:
        out(_row(result.simulator))
    out("-" * 72)
    for line in format_metrics(result.metrics):
        out(line)
    return result
