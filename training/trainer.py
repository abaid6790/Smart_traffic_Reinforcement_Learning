"""Trains a Q-Learning agent by playing many simulated episodes.

``Trainer.train()`` plays episodes one after another.  After each one it records a row of
statistics (and appends it to a CSV file straight away, so nothing is lost if the program
is stopped or crashes), lets the agent's epsilon decay, and calls ``on_episode`` so a
screen can show progress.  Training can be paused and stopped from outside (for example a
button on another thread) with ``pause()``, ``resume()`` and ``stop()``; a stop takes
effect at the end of the current episode, which only lasts a fraction of a second, so the
model is always left in a consistent state.

Seeds: episode ``i`` of a training run uses traffic seed ``base_seed + i``.  Tests and
experiments use a separate, far-away range (``evaluation_seed``), and the checks made during
training use a third one (``validation_seed``), so a trained agent is never judged on
traffic it practised on.

Keeping the best policy: the greedy policy of a Q-table that is still learning can swing
between good and bad from one episode to the next (the table keeps moving on every update).
So every ``rl.validation_every`` episodes the current policy is tried, with exploration
off, on ``rl.validation_runs`` fixed validation runs, scored by the average waiting time of
all vehicles (lower is better).  The best table seen is remembered and put back into the
agent when training ends, so the saved model is the best one found, not just the last.
"""

from __future__ import annotations

import copy
import csv
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path

from agents.q_learning import QLearningAgent
from config.settings import SCENARIO_NAMES, Settings
from controllers.rl_controller import QLearningController
from environment.rl_env import TrafficEnv
from evaluation.seeds import training_seed, validation_seed
from simulation.runner import run_episode

@dataclass(frozen=True)
class EpisodeStats:
    """What happened in one training episode (one row of the CSV file)."""

    episode: int  # 1, 2, 3, ...
    scenario: str
    seed: int
    epsilon: float  # the exploration rate used during this episode
    total_reward: float
    decisions: int
    average_waiting_time: float | None  # served vehicles; None if none were served
    average_queue_length: float | None
    max_queue_length: int
    vehicles_served: int
    vehicles_arrived: int
    light_switches: int
    safety_violations: int
    q_table_change: float  # average absolute TD error: how much the agent was still learning
    validation_waiting_time: float | None = None  # set on episodes where the policy was checked


CSV_COLUMNS: tuple[str, ...] = tuple(f.name for f in fields(EpisodeStats))


@dataclass
class TrainingResult:
    agent: QLearningAgent
    stats: list[EpisodeStats] = field(default_factory=list)
    requested_episodes: int = 0
    stopped_early: bool = False
    seconds: float = 0.0
    log_path: Path | None = None
    best_episode: int | None = None  # episode whose policy was kept (None: validation off)
    best_score: float | None = None  # its validation average waiting time (s)

    @property
    def episodes_done(self) -> int:
        return len(self.stats)


def rolling_mean(values: Sequence[float | None], window: int) -> list[float | None]:
    """Moving average over the last ``window`` values (ignoring missing ones)."""
    if window < 1:
        raise ValueError("window must be at least 1")
    out: list[float | None] = []
    for i in range(len(values)):
        chunk = [v for v in values[max(0, i - window + 1): i + 1] if v is not None]
        out.append(sum(chunk) / len(chunk) if chunk else None)
    return out


class Trainer:
    """Plays training episodes for one agent."""

    def __init__(self, settings: Settings, agent: QLearningAgent | None = None,
                 scenarios: Sequence[str] | None = None) -> None:
        self.settings = settings.validate()
        self.agent = agent or QLearningAgent(self.settings.rl, seed=self.settings.traffic.seed)
        self.scenarios = list(scenarios) if scenarios else [self.settings.traffic.scenario]
        unknown = [s for s in self.scenarios if s not in SCENARIO_NAMES]
        if unknown:
            raise ValueError(f"Unknown scenario(s): {', '.join(unknown)} "
                             f"(valid: {', '.join(SCENARIO_NAMES)})")
        self._envs = {
            name: TrafficEnv(self.settings.with_changes("traffic", scenario=name))
            for name in dict.fromkeys(self.scenarios)
        }
        self._scenario_settings = {
            name: self.settings.with_changes("traffic", scenario=name) for name in self._envs}
        self._best: tuple[float, int, list[list[float]], list[list[int]]] | None = None
        self._stop = threading.Event()
        self._running = threading.Event()  # set = running, cleared = paused
        self._running.set()

    # ---- control from outside -----------------------------------------------------------------

    def stop(self) -> None:
        """Ask training to end after the current episode."""
        self._stop.set()
        self._running.set()  # a paused trainer must wake up to see the request

    def pause(self) -> None:
        self._running.clear()

    def resume(self) -> None:
        self._running.set()

    @property
    def paused(self) -> bool:
        return not self._running.is_set()

    @property
    def stop_requested(self) -> bool:
        return self._stop.is_set()

    # ---- training ---------------------------------------------------------------------------------

    def train(
        self,
        episodes: int | None = None,
        on_episode: Callable[[EpisodeStats, int], None] | None = None,
        log_path: Path | str | None = None,
    ) -> TrainingResult:
        """Train for ``episodes`` episodes (default: ``settings.rl.episodes``).

        ``on_episode(stats, total)`` is called after every episode.  ``log_path`` (a CSV
        file) gets one row per episode as it finishes.  The agent keeps what it has
        learned, so calling ``train`` again continues training.
        """
        total = self.settings.rl.episodes if episodes is None else episodes
        if not isinstance(total, int) or isinstance(total, bool) or total < 1:
            raise ValueError("episodes must be a whole number of at least 1")
        self._stop.clear()
        self._running.set()
        self._best = None
        agent = self.agent
        base_seed = self.settings.traffic.seed
        result = TrainingResult(agent=agent, requested_episodes=total,
                                log_path=Path(log_path) if log_path else None)
        started = time.perf_counter()
        writer_file = None
        try:
            writer = None
            if result.log_path is not None:
                result.log_path.parent.mkdir(parents=True, exist_ok=True)
                writer_file = result.log_path.open("w", newline="", encoding="utf-8")
                writer = csv.DictWriter(writer_file, fieldnames=CSV_COLUMNS)
                writer.writeheader()
                writer_file.flush()
            for index in range(total):
                self._running.wait()  # blocks while paused
                if self._stop.is_set():
                    result.stopped_early = True
                    break
                stats = self._play_episode(base_seed)
                if self._is_validation_episode(stats.episode, index, total):
                    stats = replace(stats, validation_waiting_time=self._validate(stats.episode))
                result.stats.append(stats)
                if writer is not None and writer_file is not None:
                    writer.writerow(_csv_row(stats))
                    writer_file.flush()
                if on_episode is not None:
                    on_episode(stats, total)
        finally:
            if writer_file is not None:
                writer_file.close()
            if self._best is not None:
                score, episode, q, visits = self._best
                agent.q, agent.visits = copy.deepcopy(q), copy.deepcopy(visits)
                result.best_episode, result.best_score = episode, score
            result.seconds = time.perf_counter() - started
        return result

    def _is_validation_episode(self, episode: int, index: int, total: int) -> bool:
        every = self.settings.rl.validation_every
        return every > 0 and (episode % every == 0 or index == total - 1)

    def _validate(self, episode: int) -> float | None:
        """Try the current greedy policy on the fixed validation runs; remember it if it is
        the best so far.  Returns the average waiting time (None if nothing could be measured)."""
        base_seed = self.settings.traffic.seed
        controller = QLearningController(self.agent)  # explore=False: epsilon 0
        scores = []
        for run in range(self.settings.rl.validation_runs):
            scenario = self.scenarios[run % len(self.scenarios)]
            metrics = run_episode(self._scenario_settings[scenario], controller,
                                  seed=validation_seed(base_seed, run)).metrics
            if metrics.average_waiting_time_all is not None:
                scores.append(metrics.average_waiting_time_all)
        if not scores:
            return None
        score = sum(scores) / len(scores)
        if self._best is None or score < self._best[0]:
            self._best = (score, episode, copy.deepcopy(self.agent.q), copy.deepcopy(self.agent.visits))
        return score

    def _play_episode(self, base_seed: int) -> EpisodeStats:
        agent = self.agent
        scenario = self.scenarios[(agent.episodes_trained) % len(self.scenarios)]
        env = self._envs[scenario]
        seed = training_seed(base_seed, agent.episodes_trained)
        epsilon = agent.epsilon
        state = env.reset(seed=seed)
        total_reward = 0.0
        errors: list[float] = []
        decisions = 0
        while True:
            action = agent.choose_action(state, env.valid_actions(), explore=True)
            next_state, reward, done, _info = env.step(action)
            errors.append(abs(agent.update(state, action, reward, next_state,
                                           next_valid_actions=env.valid_actions(),
                                           terminal=False)))
            total_reward += reward
            decisions += 1
            state = next_state
            if done:
                break
        agent.episodes_trained += 1
        agent.decay_epsilon()
        metrics = env.episode_metrics()
        return EpisodeStats(
            episode=agent.episodes_trained,
            scenario=scenario,
            seed=seed,
            epsilon=epsilon,
            total_reward=total_reward,
            decisions=decisions,
            average_waiting_time=metrics.average_waiting_time,
            average_queue_length=metrics.average_queue_length,
            max_queue_length=metrics.max_queue_length,
            vehicles_served=metrics.vehicles_served,
            vehicles_arrived=metrics.vehicles_arrived,
            light_switches=metrics.light_switches,
            safety_violations=metrics.safety_violations,
            q_table_change=sum(errors) / len(errors),
        )


def _csv_row(stats: EpisodeStats) -> dict[str, object]:
    row = asdict(stats)
    for key in ("average_waiting_time", "average_queue_length", "validation_waiting_time"):
        row[key] = "" if row[key] is None else row[key]
    return row
