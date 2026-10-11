"""The interface every traffic-light controller follows.

A controller looks at the simulator and may *ask* the light to change.  It never
touches vehicles or timers directly, and the light refuses any request that would
break a safety rule (see ``environment.traffic_light``).  Because every controller
(fixed-time and Q-Learning) works through this one small interface, they
can be run, measured and compared in exactly the same way.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.simulator import Simulator


class Controller(ABC):
    """Base class for traffic-light controllers."""

    #: Short name used in results and reports.
    name: str = "controller"

    def reset(self) -> None:
        """Forget any state.  Called at the start of every episode."""

    @abstractmethod
    def act(self, sim: Simulator) -> None:
        """Look at ``sim`` and optionally call ``sim.light.request_switch()``.

        Called once before every simulation step.
        """

    def describe(self) -> str:
        """One line explaining how this controller behaves (for reports)."""
        return self.name
