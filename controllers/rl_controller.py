"""Lets a trained Q-Learning agent run the traffic light.

It follows exactly the same decision rhythm as the training environment
(``environment.rl_env``): the agent decides while the light has a steady green, at most
every ``rl.decision_interval`` seconds, and again as soon as a green returns after a switch.
Like every controller it can only *request* a switch, so the safety rules of the traffic
light still apply.  Because it is a normal ``Controller``, ``run_episode`` measures it
exactly as it measures the fixed-time controller.

By default epsilon is 0 (``explore=False``): the agent always does what it has learned.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agents.q_learning import QLearningAgent
from controllers.base import Controller
from environment.enums import LightStage
from environment.rl_env import KEEP, SWITCH, encode_state

if TYPE_CHECKING:
    from simulation.simulator import Simulator

_EPS = 1e-9


class QLearningController(Controller):
    name = "q-learning"

    def __init__(self, agent: QLearningAgent, explore: bool = False) -> None:
        self.agent = agent
        self.explore = explore
        self.decisions = 0
        self.reset()

    def reset(self) -> None:
        self._next_decision = 0.0
        self.decisions = 0

    def act(self, sim: Simulator) -> None:
        light = sim.light
        if light.stage is not LightStage.GREEN or sim.time < self._next_decision - _EPS:
            return
        valid = [KEEP, SWITCH] if light.can_switch() else [KEEP]
        state = encode_state(sim, self.agent.rl)
        action = self.agent.choose_action(state, valid, explore=self.explore)
        self.decisions += 1
        if action == SWITCH:
            light.request_switch()  # refused (and so harmless) if the minimum green is not over
        # Like the training environment: the next decision comes one decision interval
        # later, but never while the light is changing (``act`` returns early then), so after
        # a switch it is made as soon as the new green begins.
        self._next_decision = sim.time + self.agent.rl.decision_interval

    def describe(self) -> str:
        rl = self.agent.rl
        mode = "exploring" if self.explore else "learned policy, epsilon 0"
        return (f"Q-Learning agent ({mode}; trained {self.agent.episodes_trained} episodes; "
                f"decides every {rl.decision_interval:g} s)")
