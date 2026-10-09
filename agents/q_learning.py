"""Tabular Q-Learning: a table of "how good is each action in each state".

The table has one row per state (18) and one column per action (KEEP, SWITCH), so 36
numbers in total.  After every decision the agent nudges one entry towards what it just
saw (the *update rule*)::

    Q(s, a)  <-  Q(s, a) + learning_rate * ( reward + discount * max Q(s', a')  -  Q(s, a) )

* ``learning_rate`` - how far one experience moves the number (0 to 1).
* ``discount_factor`` - how much the future matters compared with the next reward.

**Exploration versus exploitation** (epsilon-greedy): while training, with probability
``epsilon`` the agent tries a random action, otherwise it takes the best one it knows.
``epsilon`` starts high (explore a lot) and shrinks by ``epsilon_decay`` after every
episode, but never below ``epsilon_min``.  When the trained agent is *tested*, epsilon is 0
(``explore=False``): it always uses what it has learned.

Only actions that can have an effect are considered (``valid_actions``): a switch the
traffic light would refuse is never chosen or used as the "best future action".
"""

from __future__ import annotations

import json
import math
import os
import random
from datetime import datetime
from pathlib import Path
from typing import Any

from config.settings import RLConfig
from environment.rl_env import (
    ACTION_NAMES,
    ACTIONS,
    NUM_ACTIONS,
    NUM_STATES,
    State,
    all_states,
    describe_state,
    state_index,
)

MODEL_FORMAT = "smart-traffic-rl-q-table"
MODEL_VERSION = 1


class ModelError(Exception):
    """A model file is missing, damaged or does not fit the current settings."""


def _design(rl: RLConfig) -> dict[str, Any]:
    """The settings that decide what a state or a reward *means*."""
    return {
        "num_states": NUM_STATES,
        "num_actions": NUM_ACTIONS,
        "medium_traffic": rl.medium_traffic,
        "high_traffic": rl.high_traffic,
        "decision_interval": rl.decision_interval,
    }


class QLearningAgent:
    """A Q-table with epsilon-greedy action choice."""

    def __init__(self, rl: RLConfig | None = None, seed: int | None = 0) -> None:
        problems = (rl or RLConfig()).problems()
        if problems:
            raise ValueError("Invalid learning settings: " + " ".join(problems))
        self.rl = rl or RLConfig()
        self._seed = seed
        self.rng = random.Random(seed)
        self.info: dict[str, Any] = {}
        self.reset()

    # ---- the table ---------------------------------------------------------------------------

    def reset(self) -> None:
        """Forget everything learned: zero table, epsilon back to its starting value."""
        self.q: list[list[float]] = [[0.0] * NUM_ACTIONS for _ in range(NUM_STATES)]
        self.visits: list[list[int]] = [[0] * NUM_ACTIONS for _ in range(NUM_STATES)]
        self.epsilon = self.rl.epsilon
        self.episodes_trained = 0
        self.updates = 0
        self.rng = random.Random(self._seed)
        self.info = {}

    def get_q_value(self, state: State, action: int) -> float:
        """The learned value of taking ``action`` in ``state``."""
        return self.q[state_index(state)][self._check_action(action)]

    def best_action(self, state: State, valid_actions: list[int] | None = None,
                    break_ties_randomly: bool = False) -> int:
        """The valid action with the highest Q-value.

        Ties (for example in a state never visited) go to the lowest-numbered action,
        which is KEEP, or are broken randomly when ``break_ties_randomly`` is set.
        """
        valid = self._valid(valid_actions)
        row = self.q[state_index(state)]
        best = max(row[a] for a in valid)
        winners = [a for a in valid if row[a] == best]
        return self.rng.choice(winners) if break_ties_randomly else winners[0]

    def choose_action(self, state: State, valid_actions: list[int] | None = None,
                      explore: bool = True) -> int:
        """Epsilon-greedy choice.  With ``explore=False`` epsilon is treated as 0."""
        valid = self._valid(valid_actions)
        if explore and self.rng.random() < self.epsilon:
            return self.rng.choice(valid)
        return self.best_action(state, valid, break_ties_randomly=explore)

    def update(self, state: State, action: int, reward: float, next_state: State,
               next_valid_actions: list[int] | None = None, terminal: bool = False) -> float:
        """Learn from one experience.  Returns the TD error (how surprised the agent was).

        ``terminal`` should be True only if nothing can happen after ``next_state``.
        Running out of simulated time is *not* terminal: the state does not contain the
        clock, so the value of the next state is still a sensible guess.
        """
        if not math.isfinite(reward):
            raise ValueError(f"The reward must be a finite number (got {reward}).")
        s, ns = state_index(state), state_index(next_state)
        action = self._check_action(action)
        future = 0.0
        if not terminal:
            valid = self._valid(next_valid_actions)
            future = max(self.q[ns][a] for a in valid)
        target = reward + self.rl.discount_factor * future
        error = target - self.q[s][action]
        self.q[s][action] += self.rl.learning_rate * error
        self.visits[s][action] += 1
        self.updates += 1
        return error

    def decay_epsilon(self) -> float:
        """Shrink epsilon after an episode (never below ``epsilon_min``)."""
        self.epsilon = max(self.rl.epsilon_min, self.epsilon * self.rl.epsilon_decay)
        return self.epsilon

    # ---- looking at what was learned ---------------------------------------------------------------

    def policy_table(self) -> list[dict[str, Any]]:
        """One row per state: its description, Q-values, visit counts and preferred action."""
        rows = []
        for state in all_states():
            i = state_index(state)
            visited = sum(self.visits[i]) > 0
            rows.append({
                "state": state,
                "description": describe_state(state),
                "q_keep": self.q[i][ACTIONS[0]],
                "q_switch": self.q[i][ACTIONS[1]],
                "visits_keep": self.visits[i][0],
                "visits_switch": self.visits[i][1],
                "best": ACTION_NAMES[self.best_action(state)] if visited else "(never visited)",
            })
        return rows

    # ---- saving and loading ------------------------------------------------------------------------

    def save(self, path: Path | str, **training_info: Any) -> Path:
        """Write the model to a JSON file (safely: a half-written file never replaces a good one).

        Extra keyword arguments (for example ``scenarios=[...]``) are stored as training
        information next to the automatic ones.
        """
        path = Path(path)
        rl = self.rl
        training = {
            "episodes": self.episodes_trained,
            "updates": self.updates,
            "final_epsilon": self.epsilon,
            **{k: v for k, v in training_info.items()},
        }
        data = {
            "format": MODEL_FORMAT,
            "version": MODEL_VERSION,
            "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "training": training,
            "parameters": {
                "learning_rate": rl.learning_rate,
                "discount_factor": rl.discount_factor,
                "epsilon_start": rl.epsilon,
                "epsilon_decay": rl.epsilon_decay,
                "epsilon_min": rl.epsilon_min,
            },
            "reward": {
                "switch_penalty": rl.switch_penalty,
                "queue_limit": rl.queue_limit,
                "queue_penalty": rl.queue_penalty,
            },
            "state_design": _design(rl),
            "q_table": self.q,
            "visits": self.visits,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        try:
            temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()
        self.info = {k: v for k, v in data.items() if k not in ("q_table", "visits")}
        return path

    @classmethod
    def load(cls, path: Path | str, rl: RLConfig | None = None, seed: int | None = 0) -> QLearningAgent:
        """Read a model file.  Raises :class:`ModelError` with a plain explanation if the
        file is missing, damaged, or was trained with a different state design than
        ``rl`` describes (the numbers would then mean something else)."""
        path = Path(path)
        data = _read_model_file(path)
        agent = cls(rl, seed=seed)
        mismatches = [
            f"{name}: model has {saved}, current settings have {_design(agent.rl)[name]}"
            for name, saved in data["state_design"].items()
            if name in _design(agent.rl) and _design(agent.rl)[name] != saved
        ]
        if mismatches:
            raise ModelError(
                f"The model {path.name} was trained with a different state design "
                f"({'; '.join(mismatches)}). Train a new model or change the settings back."
            )
        agent.q = [[float(v) for v in row] for row in data["q_table"]]
        agent.visits = [[int(v) for v in row] for row in data["visits"]]
        training = data["training"]
        agent.episodes_trained = int(training["episodes"])
        agent.updates = int(training.get("updates", 0))
        agent.epsilon = float(training.get("final_epsilon", agent.rl.epsilon_min))
        agent.info = {k: v for k, v in data.items() if k not in ("q_table", "visits")}
        return agent

    # ---- helpers -------------------------------------------------------------------------------------

    @staticmethod
    def _check_action(action: int) -> int:
        if action not in ACTIONS or isinstance(action, bool):
            raise ValueError(f"Unknown action {action!r}; use KEEP (0) or SWITCH (1).")
        return int(action)

    def _valid(self, valid_actions: list[int] | None) -> list[int]:
        if valid_actions is None:
            return list(ACTIONS)
        if not valid_actions:
            raise ValueError("There must be at least one valid action.")
        return [self._check_action(a) for a in valid_actions]


def _read_model_file(path: Path) -> dict[str, Any]:
    """Read and strictly check a model file; every problem becomes a ModelError."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ModelError(f"Model file not found: {path}") from None
    except UnicodeDecodeError:
        raise ModelError(f"{path.name} is not a text file, so it is not a saved model.") from None
    except OSError as exc:
        raise ModelError(f"Could not read {path}: {exc.strerror or exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ModelError(f"{path.name} is damaged or not a model file "
                         f"(invalid JSON at line {exc.lineno}).") from None
    if not isinstance(data, dict) or data.get("format") != MODEL_FORMAT:
        raise ModelError(f"{path.name} is not a model saved by this program.")
    if data.get("version") != MODEL_VERSION:
        raise ModelError(f"{path.name} has model version {data.get('version')!r}; "
                         f"this program understands version {MODEL_VERSION}.")
    for key in ("training", "parameters", "state_design", "q_table", "visits"):
        if key not in data:
            raise ModelError(f"{path.name} is incomplete (missing '{key}').")
    for key in ("training", "parameters", "state_design"):
        if not isinstance(data[key], dict):
            raise ModelError(f"{path.name} is damaged ('{key}' should be a group of values).")
    if "episodes" not in data["training"]:
        raise ModelError(f"{path.name} is incomplete (missing training episodes).")
    episodes = data["training"]["episodes"]
    if not isinstance(episodes, int) or isinstance(episodes, bool) or episodes < 0:
        raise ModelError(f"{path.name} is damaged (training episodes: {episodes!r}).")
    _check_table(path, "q_table", data["q_table"], numbers=float)
    _check_table(path, "visits", data["visits"], numbers=int)
    return data


def _check_table(path: Path, name: str, table: Any, numbers: type) -> None:
    ok = isinstance(table, list) and len(table) == NUM_STATES and all(
        isinstance(row, list) and len(row) == NUM_ACTIONS for row in table)
    if not ok:
        raise ModelError(f"{path.name} is damaged: '{name}' must be {NUM_STATES} rows of "
                         f"{NUM_ACTIONS} numbers (it does not fit this program's state design).")
    for row in table:
        for value in row:
            good = isinstance(value, (int, float)) and not isinstance(value, bool) \
                and math.isfinite(value)
            if numbers is int:
                good = good and float(value).is_integer() and value >= 0
            if not good:
                raise ModelError(f"{path.name} is damaged: '{name}' contains {value!r}.")
