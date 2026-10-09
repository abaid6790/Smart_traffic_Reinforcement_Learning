"""The traditional fixed-time controller: the baseline for the RL agent.

It ignores traffic completely and simply repeats the same cycle::

    NS green -> yellow -> all-red -> EW green -> yellow -> all-red -> ...

The green times come from ``settings.fixed`` (default 30 s each); yellow and
all-red come from ``settings.lights``.  Because it never looks at the queues, it
is exactly what a plain timed signal does, which makes it an honest baseline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from config.settings import Settings
from controllers.base import Controller
from environment.enums import LightStage, Phase

if TYPE_CHECKING:
    from simulation.simulator import Simulator

# Tolerance for accumulated floating-point error when comparing times.
_EPS = 1e-6


class FixedTimeController(Controller):
    """Switches the light after a fixed green time for each phase."""

    name = "fixed"

    def __init__(self, settings: Settings) -> None:
        settings.validate()
        self._green = {
            Phase.NS: settings.fixed.ns_green,
            Phase.EW: settings.fixed.ew_green,
        }
        self._yellow = settings.lights.yellow
        self._all_red = settings.lights.all_red

    @property
    def cycle_time(self) -> float:
        """Length of one complete cycle through both phases (seconds)."""
        return sum(self._green.values()) + 2.0 * (self._yellow + self._all_red)

    def act(self, sim: Simulator) -> None:
        light = sim.light
        if (
            light.stage is LightStage.GREEN
            and light.stage_time >= self._green[light.phase] - _EPS
        ):
            light.request_switch()

    def describe(self) -> str:
        return (
            f"Fixed-time: NS green {self._green[Phase.NS]:g} s, "
            f"EW green {self._green[Phase.EW]:g} s, yellow {self._yellow:g} s, "
            f"all-red {self._all_red:g} s (cycle {self.cycle_time:g} s)"
        )
