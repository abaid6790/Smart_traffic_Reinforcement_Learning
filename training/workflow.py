"""Training as a whole job: check the plan, train, save the model, the log and the graphs.

The command line (`main.py --train`) and the window's training screen both need the
same steps, so the steps for the window live here as plain, tested functions.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from agents.q_learning import QLearningAgent
from config.settings import SCENARIO_NAMES, Settings
from training.trainer import EpisodeStats, Trainer

log = logging.getLogger(__name__)

MAX_EPISODES = 100_000


@dataclass
class TrainingPlan:
    """What the user asked for."""

    settings: Settings
    scenarios: list[str]
    episodes: int
    model_path: Path
    continue_training: bool = False  # keep training the model in the file
    replace_existing: bool = False  # the user agreed to overwrite an existing model

    def problems(self) -> list[str]:
        """Everything wrong with the plan, in plain English (empty list = fine)."""
        found: list[str] = []
        if not self.scenarios:
            found.append("Choose at least one scenario to train on.")
        unknown = [s for s in self.scenarios if s not in SCENARIO_NAMES]
        if unknown:
            found.append(f"Unknown scenario(s): {', '.join(unknown)}.")
        if (not isinstance(self.episodes, int) or isinstance(self.episodes, bool)
                or not 1 <= self.episodes <= MAX_EPISODES):
            found.append(f"Episodes must be a whole number from 1 to {MAX_EPISODES}.")
        if self.continue_training and not self.model_path.is_file():
            found.append("There is no model to continue training yet.")
        return found

    @property
    def would_replace_model(self) -> bool:
        return self.model_path.exists() and not self.continue_training


@dataclass
class TrainingOutcome:
    model_path: Path
    episodes_done: int
    seconds: float
    stopped_early: bool
    best_episode: int | None
    best_score: float | None
    safety_violations: int
    log_path: Path | None
    graph_files: list[Path] = field(default_factory=list)
    graph_note: str = ""
    saved: bool = True

    @property
    def safe(self) -> bool:
        return self.safety_violations == 0


def run_training(
    plan: TrainingPlan,
    csv_dir: Path,
    graph_dir: Path,
    on_episode: Callable[[EpisodeStats, int], None] | None = None,
    trainer_out: list[Trainer] | None = None,
    should_stop: Callable[[], bool] | None = None,
    wait_if_paused: Callable[[], None] | None = None,
) -> TrainingOutcome:
    """Run the plan.  Saves the model even when stopped early (it is always consistent).

    ``trainer_out`` receives the Trainer so another thread can pause or stop it.
    ``should_stop`` and ``wait_if_paused`` are polled after every episode.
    """
    problems = plan.problems()
    if problems:
        raise ValueError(" ".join(problems))
    if plan.would_replace_model and not plan.replace_existing:
        raise ValueError(f"{plan.model_path.name} already exists; confirm that it may be replaced.")
    settings = plan.settings
    agent = (QLearningAgent.load(plan.model_path, settings.rl, seed=settings.traffic.seed)
             if plan.continue_training
             else QLearningAgent(settings.rl, seed=settings.traffic.seed))
    trainer = Trainer(settings, agent, plan.scenarios)
    if trainer_out is not None:
        trainer_out.append(trainer)
    history: list[EpisodeStats] = []
    stamp = f"{datetime.now():%Y%m%d_%H%M%S}"
    log_path = Path(csv_dir) / f"training_{stamp}.csv"

    def progress(stats: EpisodeStats, total: int) -> None:
        history.append(stats)
        if on_episode is not None:
            on_episode(stats, total)
        if should_stop is not None and should_stop():
            trainer.stop()
        if wait_if_paused is not None:
            wait_if_paused()

    result = trainer.train(plan.episodes, on_episode=progress, log_path=log_path)
    stopped = result.stopped_early or (should_stop is not None and should_stop())
    info = {"scenarios": trainer.scenarios, "base_seed": settings.traffic.seed,
            "episode_seconds": settings.simulation.duration, "stopped_early": stopped,
            "best_episode": result.best_episode, "best_validation_waiting_time": result.best_score,
            "validation_runs": settings.rl.validation_runs}
    saved = plan.model_path
    if result.episodes_done > 0:
        saved = agent.save(plan.model_path, **info)
    outcome = TrainingOutcome(
        saved=result.episodes_done > 0, model_path=saved, episodes_done=result.episodes_done, seconds=result.seconds,
        stopped_early=stopped, best_episode=result.best_episode, best_score=result.best_score,
        safety_violations=sum(h.safety_violations for h in history), log_path=log_path)
    if len(history) >= 2:
        try:
            from evaluation.graphs import save_training_graphs
            outcome.graph_files = list(save_training_graphs(history, Path(graph_dir), stamp))
        except ImportError:
            outcome.graph_note = "matplotlib is not installed, so no graphs were drawn."
        except Exception:  # noqa: BLE001 - the model is already saved; graphs are a bonus
            log.exception("Training graphs could not be saved")
            outcome.graph_note = "The model was saved, but the graphs could not be drawn (see the log)."
    log.info("Training from the window finished: %d episodes, model %s", outcome.episodes_done, saved)
    return outcome
