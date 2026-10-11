"""The traffic light and its safety rules.

The light is a small state machine:

    GREEN (one phase) -> YELLOW -> ALL_RED -> GREEN (the other phase) -> ...

Whoever controls the light (a fixed timer or the learning agent) can only
*ask* for a switch.  The light enforces the rules itself:

* a request is ignored until the minimum green time has passed;
* the light switches on its own once the maximum green time is reached;
* every switch goes through yellow and an all-red interval;
* the two phases can never be open at the same time.

Because the rules live here, no controller can bypass them.
"""

from __future__ import annotations

from config.settings import TrafficLightConfig
from environment.enums import ALL_DIRECTIONS, Direction, LightStage, Phase, SignalColor

_EPS = 1e-9


class TrafficLight:
    """A two-phase traffic light with built-in safety constraints."""

    def __init__(self, config: TrafficLightConfig) -> None:
        self._config = config
        self.phase: Phase = Phase.from_name(config.initial_phase)
        self.stage: LightStage = LightStage.GREEN
        self.stage_time: float = 0.0
        self.switch_count: int = 0
        self.reset()

    def reset(self) -> None:
        """Return to the initial state: initial phase green, time zero."""
        self.phase = Phase.from_name(self._config.initial_phase)
        self.stage = LightStage.GREEN
        self.stage_time = 0.0
        self.switch_count = 0

    # ---- what drivers see -------------------------------------------------

    def color(self, direction: Direction) -> SignalColor:
        """Signal shown to vehicles on ``direction``."""
        if direction.phase is not self.phase or self.stage is LightStage.ALL_RED:
            return SignalColor.RED
        if self.stage is LightStage.YELLOW:
            return SignalColor.YELLOW
        return SignalColor.GREEN

    def colors(self) -> dict[Direction, SignalColor]:
        return {direction: self.color(direction) for direction in ALL_DIRECTIONS}

    def is_conflict_free(self) -> bool:
        """True if at most one pair of roads is allowed to move."""
        open_phases = {
            d.phase for d in ALL_DIRECTIONS if self.color(d) is not SignalColor.RED
        }
        return len(open_phases) <= 1

    # ---- control ------------------------------------------------------------

    def can_switch(self) -> bool:
        """True if a switch request would be accepted right now."""
        return (
            self.stage is LightStage.GREEN
            and self.stage_time >= self._config.min_green - _EPS
        )

    def request_switch(self) -> bool:
        """Ask for a phase change.  Returns True if it was accepted.

        The request is ignored (returns False) unless the light is green and
        the minimum green time has passed.
        """
        if not self.can_switch():
            return False
        self._advance_stage()
        self.stage_time = 0.0
        return True

    def update(self, dt: float) -> None:
        """Advance the light's clock by ``dt`` seconds.

        Any time left over after a stage ends carries into the next stage, so
        timings stay exact even when they are not a multiple of ``dt``.
        """
        self.stage_time += dt
        duration = self._stage_duration()
        while self.stage_time >= duration - _EPS:
            self.stage_time = max(0.0, self.stage_time - duration)
            self._advance_stage()
            duration = self._stage_duration()

    def time_left_in_stage(self) -> float:
        """Seconds until this stage ends by itself."""
        return max(0.0, self._stage_duration() - self.stage_time)

    def describe(self) -> str:
        """Short text such as ``'NS GREEN 12.5s'`` for logs and the UI."""
        return f"{self.phase.value} {self.stage.value} {self.stage_time:.1f}s"

    # ---- internals -------------------------------------------------------------

    def _stage_duration(self) -> float:
        if self.stage is LightStage.GREEN:
            return self._config.max_green
        if self.stage is LightStage.YELLOW:
            return self._config.yellow
        return self._config.all_red

    def _advance_stage(self) -> None:
        if self.stage is LightStage.GREEN:
            self.stage = LightStage.YELLOW
            self.switch_count += 1
        elif self.stage is LightStage.YELLOW:
            self.stage = LightStage.ALL_RED
        else:
            self.stage = LightStage.GREEN
            self.phase = self.phase.other
