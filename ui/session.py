"""The running simulation behind the window.  Plain Python (no pygame needed).

A :class:`SimulationSession` owns a simulator, a controller and a metrics collector,
and knows how to move them forward in step with real time: pause, play, one step,
faster, slower, restart.  The window only draws what the session holds and tells it
what the user asked for, so all of this can be tested without a screen.

Running through the window gives exactly the same results as running without one:
the window never changes what the simulator does, only how fast it is watched.
"""

from __future__ import annotations

from config.settings import MAX_SEED, SPEED_CHOICES, Settings
from controllers.base import Controller
from evaluation.metrics import EpisodeMetrics, MetricsCollector
from simulation.simulator import Simulator
from ui.snapshot import Snapshot, capture

_EPS = 1e-9

# A slow frame (a window being dragged, say) must not make the simulation leap forward.
MAX_FRAME_SECONDS = 0.1
# Safety net: never run more than this many steps in a single call.
MAX_STEPS_PER_CALL = 1_000


class SimulationSession:
    """A simulation that can be played, paused, stepped, sped up and restarted."""

    def __init__(
        self,
        settings: Settings,
        controller: Controller,
        speed: float | None = None,
        paused: bool = False,
    ) -> None:
        self.settings = settings.validate()
        self.controller = controller
        self.speed = self.settings.display.simulation_speed
        if speed is not None:
            self.set_speed(speed)
        self.paused = paused
        self.seed = self.settings.traffic.seed
        self.restart()

    # ---- playback ---------------------------------------------------------------

    @property
    def finished(self) -> bool:
        return self.sim.finished

    @property
    def dt(self) -> float:
        return self.sim.dt

    @property
    def alpha(self) -> float:
        """How far through the latest simulation step the picture is (0 to 1)."""
        if self.sim.finished:
            return 1.0
        return max(0.0, min(1.0, self._accumulator / self.dt))

    @property
    def display_time(self) -> float:
        """The simulated time the picture currently shows."""
        return self.previous.time + (self.current.time - self.previous.time) * self.alpha

    def advance(self, real_seconds: float) -> int:
        """Move the simulation forward for ``real_seconds`` of real time.

        Returns the number of simulation steps taken.  Does nothing while paused or
        once the run has finished.
        """
        if self.paused or self.sim.finished or real_seconds <= 0:
            return 0
        self._accumulator += min(real_seconds, MAX_FRAME_SECONDS) * self.speed
        steps = 0
        while (
            self._accumulator >= self.dt - _EPS
            and not self.sim.finished
            and steps < MAX_STEPS_PER_CALL
        ):
            self._step()
            self._accumulator -= self.dt
            steps += 1
        if self.sim.finished or steps == MAX_STEPS_PER_CALL:
            self._accumulator = 0.0
        return steps

    def step_once(self) -> bool:
        """Run exactly one simulation step (used while paused).  Returns False if the
        run has already finished."""
        if self.sim.finished:
            return False
        self._step()
        # Show the new state straight away, and keep showing it when playing resumes.
        self.previous = self.current
        self._accumulator = 0.0
        return True

    def toggle_pause(self) -> None:
        self.paused = not self.paused

    # ---- speed ------------------------------------------------------------------------

    def set_speed(self, speed: float) -> None:
        if speed not in SPEED_CHOICES:
            choices = ", ".join(f"{s:g}x" for s in SPEED_CHOICES)
            raise ValueError(f"Speed must be one of {choices} (got {speed}).")
        self.speed = speed

    def faster(self) -> None:
        index = SPEED_CHOICES.index(self.speed)
        self.speed = SPEED_CHOICES[min(index + 1, len(SPEED_CHOICES) - 1)]

    def slower(self) -> None:
        index = SPEED_CHOICES.index(self.speed)
        self.speed = SPEED_CHOICES[max(index - 1, 0)]

    # ---- starting over ---------------------------------------------------------------------

    def restart(self, seed: int | None = None) -> None:
        """Start a new run.  Without ``seed`` the same traffic is replayed."""
        if seed is not None:
            self.seed = seed
        self.sim = Simulator(self.settings)
        self.sim.reset(seed=self.seed)
        self.controller.reset()
        self.collector = MetricsCollector()
        self._accumulator = 0.0
        self.previous = self.current = capture(self.sim)

    def new_seed(self) -> None:
        """Start a new run with different traffic (the next seed)."""
        self.restart((self.seed + 1) % (MAX_SEED + 1))

    # ---- measurements ------------------------------------------------------------------------

    def live_metrics(self) -> EpisodeMetrics:
        """The metrics of the run so far."""
        return self.collector.result(self.sim, self.controller.name)

    # ---- internals ------------------------------------------------------------------------------

    def _step(self) -> None:
        self.controller.act(self.sim)
        # The signals vehicles obey during this step are those after the controller
        # has acted and before the step runs, so that is the "before" picture.
        self.previous = capture(self.sim)
        self.sim.step()
        self.collector.record(self.sim)
        self.current = capture(self.sim)

    @property
    def state(self) -> Snapshot:
        """The snapshot whose signals are on display."""
        return self.previous
