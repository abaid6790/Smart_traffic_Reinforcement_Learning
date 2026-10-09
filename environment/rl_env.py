"""The reinforcement-learning environment: the simulator seen as "state, action, reward".

An agent plays the environment like this::

    env = TrafficEnv(settings)
    state = env.reset(seed=7)
    while True:
        action = agent.choose(state, env.valid_actions())   # KEEP or SWITCH
        state, reward, done, info = env.step(action)
        if done:
            break

The design is deliberately small so a Q-table can learn it (exact formulas are in
``docs/RL_ENVIRONMENT.md``):

* **State** - three numbers: how busy the North/South roads are (0 low, 1 medium,
  2 high), how busy East/West are, and which pair currently has the green light
  (0 = NS, 1 = EW).  That is 3 x 3 x 2 = 18 states.
* **Actions** - ``KEEP`` the current phase or ``SWITCH`` to the other one.  The agent
  never touches timers; it can only *ask*, and the traffic light refuses anything that
  breaks a safety rule (minimum green, yellow, all-red).
* **A step is one decision**: the environment applies the action, then simulates
  ``rl.decision_interval`` seconds (and, if a switch is under way, waits until the
  yellow and all-red phases are over).  So the agent only ever sees a state in which
  one pair has a steady green light.
* **Reward** - the fall in the number of waiting vehicles, minus a penalty for every
  light switch, minus a penalty for each vehicle waiting beyond a limit.

Traffic depends only on the seed and scenario, never on the agent, so a trained agent
and the fixed-time controller can be tested on exactly the same vehicles.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from config.settings import RLConfig, Settings
from environment.enums import LightStage, Phase
from evaluation.metrics import EpisodeMetrics, MetricsCollector
from simulation.simulator import Simulator

KEEP = 0
SWITCH = 1
ACTIONS: tuple[int, ...] = (KEEP, SWITCH)
ACTION_NAMES = {KEEP: "KEEP", SWITCH: "SWITCH"}

LEVEL_NAMES = ("low", "medium", "high")
PHASES: tuple[Phase, ...] = (Phase.NS, Phase.EW)  # position in this tuple = phase number

NUM_LEVELS = len(LEVEL_NAMES)
NUM_STATES = NUM_LEVELS * NUM_LEVELS * len(PHASES)  # 18
NUM_ACTIONS = len(ACTIONS)

#: (north/south level, east/west level, phase number)
State = tuple[int, int, int]

_EPS = 1e-9


class StepResult(NamedTuple):
    state: State
    reward: float
    done: bool
    info: dict[str, Any]


# ---- the state, as plain functions (a controller can use them without an environment) ------


def traffic_level(vehicles: int, rl: RLConfig) -> int:
    """0 = low, 1 = medium, 2 = high for ``vehicles`` approaching a road pair."""
    if vehicles >= rl.high_traffic:
        return 2
    if vehicles >= rl.medium_traffic:
        return 1
    return 0


def encode_state(sim: Simulator, rl: RLConfig) -> State:
    """The discrete state of ``sim``."""
    counts = sim.approach_counts()
    busy = {phase: sum(n for d, n in counts.items() if d.phase is phase) for phase in PHASES}
    return (
        traffic_level(busy[Phase.NS], rl),
        traffic_level(busy[Phase.EW], rl),
        PHASES.index(sim.light.phase),
    )


def state_index(state: State) -> int:
    """A unique number 0..17 for a state (the row of a Q-table)."""
    ns, ew, phase = state
    if not (0 <= ns < NUM_LEVELS and 0 <= ew < NUM_LEVELS and 0 <= phase < len(PHASES)):
        raise ValueError(f"Not a valid state: {state!r}")
    return (ns * NUM_LEVELS + ew) * len(PHASES) + phase


def all_states() -> list[State]:
    """Every possible state, in ``state_index`` order."""
    return [
        (ns, ew, phase)
        for ns in range(NUM_LEVELS)
        for ew in range(NUM_LEVELS)
        for phase in range(len(PHASES))
    ]


def describe_state(state: State) -> str:
    """Plain English, e.g. ``'NS traffic high, EW traffic low, NS has green'``."""
    ns, ew, phase = state
    state_index(state)  # validates
    return (f"NS traffic {LEVEL_NAMES[ns]}, EW traffic {LEVEL_NAMES[ew]}, "
            f"{PHASES[phase].value} has green")


# ---- the environment ----------------------------------------------------------------------------


class TrafficEnv:
    """One intersection as a reinforcement-learning environment."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = (settings or Settings()).validate()
        self.rl = self.settings.rl
        self.sim = Simulator(self.settings)
        self._collector = MetricsCollector()
        self._seed: int | None = None
        self._start_waiting = 0
        self._start_switches = 0
        self.decisions = 0
        self.reset()

    # ---- the four calls from the project brief --------------------------------------------

    def reset(self, seed: int | None = None) -> State:
        """Start a new episode and return its first state.

        ``seed`` picks the traffic (default: the seed in the settings).
        """
        self.sim.reset(seed=seed)
        self._seed = seed if seed is not None else self.settings.traffic.seed
        self._collector = MetricsCollector()
        self._start_waiting = self.waiting_vehicles()
        self._start_switches = self.sim.light.switch_count
        self.decisions = 0
        return self.get_state()

    def get_state(self) -> State:
        """The current discrete state."""
        return encode_state(self.sim, self.rl)

    def step(self, action: int) -> StepResult:
        """Apply ``action``, simulate until the next decision, and return the outcome.

        A ``SWITCH`` the traffic light refuses (minimum green not reached yet) simply
        has no effect, is not penalised and is reported as ``info["switch_ignored"]``.
        Use :meth:`valid_actions` to avoid asking for it.
        """
        if self.done:
            raise RuntimeError("The episode is over; call reset() to start a new one.")
        if action not in ACTIONS:
            raise ValueError(f"Unknown action {action!r}; use KEEP (0) or SWITCH (1).")

        light = self.sim.light
        self._start_waiting = self.waiting_vehicles()
        self._start_switches = light.switch_count
        start_time = self.sim.time
        ignored = action == SWITCH and not light.request_switch()

        interval = self.rl.decision_interval
        while not self.sim.finished and (
            self.sim.time - start_time < interval - _EPS or light.stage is not LightStage.GREEN
        ):
            self.sim.step()
            self._collector.record(self.sim)

        self.decisions += 1
        parts = self.reward_breakdown()
        info = self.snapshot()
        info.update(
            action=ACTION_NAMES[action],
            switch_ignored=ignored,
            seconds=self.sim.time - start_time,
            reward_parts=parts,
        )
        return StepResult(self.get_state(), parts["total"], self.done, info)

    def calculate_reward(self) -> float:
        """The reward for the decision just taken (see :meth:`reward_breakdown`)."""
        return self.reward_breakdown()["total"]

    # ---- helpers --------------------------------------------------------------------------

    @property
    def done(self) -> bool:
        return self.sim.finished

    @property
    def seed(self) -> int | None:
        return self._seed

    def valid_actions(self) -> list[int]:
        """The actions that can have an effect right now (``SWITCH`` only once the
        minimum green time has passed)."""
        return list(ACTIONS) if self.sim.light.can_switch() else [KEEP]

    def waiting_vehicles(self) -> int:
        """Vehicles standing at a stop line, plus those waiting outside a full road."""
        return sum(self.sim.queue_lengths().values())

    def reward_breakdown(self) -> dict[str, float]:
        """The reward for the latest decision, split into its three parts.

        ``reduction``  waiting vehicles before the decision - waiting vehicles after it
        ``switching``  - switch_penalty x light switches during the decision
        ``excess``     - queue_penalty x vehicles waiting beyond queue_limit
        ``total``      the sum of the three
        """
        rl = self.rl
        waiting = self.waiting_vehicles()
        switches = self.sim.light.switch_count - self._start_switches
        reduction = float(self._start_waiting - waiting)
        switching = -rl.switch_penalty * switches
        excess = -rl.queue_penalty * max(0, waiting - rl.queue_limit)
        return {"reduction": reduction, "switching": switching, "excess": excess,
                "total": reduction + switching + excess}

    def snapshot(self) -> dict[str, Any]:
        """What the environment tracks: traffic, phase, waiting, queues, served, time."""
        sim = self.sim
        return {
            "time": sim.time,
            "phase": sim.light.phase.value,
            "stage": sim.light.stage.value,
            "waiting": self.waiting_vehicles(),
            "queues": {d.value: n for d, n in sim.queue_lengths().items()},
            "approaching": {d.value: n for d, n in sim.approach_counts().items()},
            "served": len(sim.completed),
            "arrived": sim.spawned,
            "switches": sim.light.switch_count,
            "decisions": self.decisions,
            "safety_violations": sim.safety_violations,
        }

    def episode_metrics(self) -> EpisodeMetrics:
        """The same measurements the fixed-time controller gets, for this episode so far."""
        return self._collector.result(self.sim, "rl-environment")
