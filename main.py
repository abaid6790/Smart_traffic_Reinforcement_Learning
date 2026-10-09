"""Smart Traffic Light Control Using Reinforcement Learning - entry point.

Current build: Phase 7 (experiments, graphs and export).  The menu arrives in a later phase; for now
this program checks your settings, can open the simulation window, run a text demo
with the fixed-time controller, can train and run the Q-Learning agent
and explains what is available.

    python main.py                 show an overview
    python main.py --window        watch the simulation in a window
    python main.py --demo          run a simulation and print a report
    python main.py --train         train the Q-Learning agent and save the model
    python main.py --experiment    compare fixed-time, tuned fixed-time and Q-Learning
    python main.py --demo --controller rl    run the trained agent
    python main.py --env-demo      play the RL environment with a random agent
    python main.py --screenshot out/frame.png
    python main.py --list-scenarios
    python main.py --write-settings
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from agents.q_learning import ModelError, QLearningAgent
from config.settings import (
    PROJECT_NAME,
    SPEED_CHOICES,
    PROJECT_VERSION,
    SCENARIO_NAMES,
    SCENARIOS,
    ConfigError,
    Settings,
)
from controllers.base import Controller
from controllers.fixed_controller import FixedTimeController
from controllers.rl_controller import QLearningController
from evaluation.experiment import MAX_RUNS, run_experiment
from evaluation.export import save_experiment
from evaluation.formatting import format_experiment
from simulation.env_demo import run_env_demo
from simulation.headless_demo import run_demo
from utils.logging_setup import setup_logging
from training.trainer import Trainer, rolling_mean
from utils.paths import (
    CSV_DIR,
    GRAPH_DIR,
    LOG_DIR,
    MODEL_DIR,
    RESULTS_DIR,
    SETTINGS_FILE,
    ensure_directories,
)

log = logging.getLogger("main")

DEFAULT_MODEL_NAME = "q_learning_model.json"

CURRENT_PHASE = "Phase 7 of 11 - experiments, graphs and export"

PYGAME_MISSING_MESSAGE = (
    "The window needs the pygame library, which is not installed.\n"
    "Install it with:  pip install -r requirements.txt"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description=f"{PROJECT_NAME} (academic simulation project)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {PROJECT_VERSION}")
    parser.add_argument("--demo", action="store_true",
                        help="run a simulation (no window) and print a text report")
    parser.add_argument("--experiment", action="store_true",
                        help="compare the controllers on identical traffic; saves a report, "
                             "CSV/JSON files and graphs")
    parser.add_argument("--runs", type=int, default=20, metavar="N",
                        help=f"runs per controller and scenario for --experiment (1-{MAX_RUNS}, default 20)")
    parser.add_argument("--experiment-scenarios", metavar="LIST",
                        help="scenarios to compare, comma separated, or 'all' (default: the --scenario one)")
    parser.add_argument("--no-tune", action="store_true",
                        help="--experiment: skip the tuned fixed-time controller")
    parser.add_argument("--no-rl", action="store_true",
                        help="--experiment: skip the Q-Learning agent (no model needed)")
    parser.add_argument("--no-graphs", action="store_true",
                        help="do not draw graphs (they need matplotlib)")
    parser.add_argument("--results-dir", type=Path, metavar="DIR",
                        help="folder for experiment files (default: results/)")
    parser.add_argument("--train", action="store_true",
                        help="train the Q-Learning agent (no window) and save the model")
    parser.add_argument("--episodes", type=int, metavar="N",
                        help="training episodes (overrides rl.episodes)")
    parser.add_argument("--train-scenarios", metavar="LIST",
                        help="scenarios to train on, comma separated, or 'all' "
                             "(default: the --scenario / settings scenario only)")
    parser.add_argument("--learning-rate", type=float, metavar="X", help="Q-Learning learning rate")
    parser.add_argument("--discount", type=float, metavar="X", help="Q-Learning discount factor")
    parser.add_argument("--epsilon", type=float, metavar="X", help="initial exploration rate")
    parser.add_argument("--epsilon-decay", type=float, metavar="X",
                        help="exploration rate is multiplied by this after every episode")
    parser.add_argument("--epsilon-min", type=float, metavar="X", help="lowest exploration rate")
    parser.add_argument("--model", type=Path, metavar="FILE",
                        help=f"model file to save to / load from (default: models/{DEFAULT_MODEL_NAME})")
    parser.add_argument("--continue-training", action="store_true",
                        help="with --train: start from the existing model instead of a new one")
    parser.add_argument("--no-log", action="store_true",
                        help="with --train: do not write the per-episode CSV log")
    parser.add_argument("--model-info", action="store_true",
                        help="show what a model file contains and what it learned")
    parser.add_argument("--controller", choices=("fixed", "rl"), default="fixed",
                        help="who controls the light in --demo, --window and --screenshot "
                             "(rl needs a trained model)")
    parser.add_argument("--env-demo", action="store_true",
                        help="play the RL environment with a random agent (no learning yet)")
    parser.add_argument("--env-episodes", type=int, default=3, metavar="N",
                        help="episodes for --env-demo (default: 3)")
    parser.add_argument("--window", action="store_true",
                        help="open the simulation window (needs pygame)")
    parser.add_argument("--speed", type=float, choices=SPEED_CHOICES, metavar="X",
                        help="starting speed of the window: "
                             + ", ".join(f"{s:g}" for s in SPEED_CHOICES))
    parser.add_argument("--paused", action="store_true",
                        help="start the window paused")
    parser.add_argument("--screenshot", type=Path, metavar="FILE.png",
                        help="save a picture of the window to a PNG file (no window opens)")
    parser.add_argument("--screenshot-at", type=float, default=120.0, metavar="SECONDS",
                        help="simulated time shown in the screenshot (default: 120)")
    parser.add_argument("--scenario", choices=SCENARIO_NAMES,
                        help="traffic scenario to use (overrides the settings file)")
    parser.add_argument("--duration", type=float, metavar="SECONDS",
                        help="simulated seconds to run (overrides the settings file)")
    parser.add_argument("--seed", type=int,
                        help="random seed; the same seed gives the same traffic")
    parser.add_argument("--ns-green", type=float, metavar="SECONDS",
                        help="fixed-time controller: North/South green time (default 30)")
    parser.add_argument("--ew-green", type=float, metavar="SECONDS",
                        help="fixed-time controller: East/West green time (default 30)")
    parser.add_argument("--report-every", type=float, default=30.0, metavar="SECONDS",
                        help="how often the demo prints a row (default: 30)")
    parser.add_argument("--config", type=Path, metavar="FILE",
                        help=f"settings file to use (default: {SETTINGS_FILE.name} if it exists)")
    parser.add_argument("--list-scenarios", action="store_true",
                        help="show the available traffic scenarios")
    parser.add_argument("--write-settings", action="store_true",
                        help="write the default settings to a JSON file you can edit")
    parser.add_argument("--force", action="store_true",
                        help="allow --write-settings or --train to replace an existing file")
    return parser


def _configure_console() -> None:
    """Make printing safe on consoles that are not UTF-8 (older Windows terminals)."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")


def _load_settings(config_path: Path | None) -> Settings:
    if config_path is not None:
        log.info("Loading settings from %s", config_path)
        return Settings.load(config_path)
    if SETTINGS_FILE.is_file():
        log.info("Loading settings from %s", SETTINGS_FILE)
        return Settings.load(SETTINGS_FILE)
    log.info("No settings file found; using defaults")
    return Settings()


def _apply_overrides(settings: Settings, args: argparse.Namespace) -> Settings:
    if args.scenario is not None:
        settings = settings.with_changes("traffic", scenario=args.scenario)
    if args.seed is not None:
        settings = settings.with_changes("traffic", seed=args.seed)
    if args.duration is not None:
        settings = settings.with_changes("simulation", duration=args.duration)
    fixed_changes = {
        name: value
        for name, value in (("ns_green", args.ns_green), ("ew_green", args.ew_green))
        if value is not None
    }
    if fixed_changes:
        settings = settings.with_changes("fixed", **fixed_changes)
    rl_changes = {
        name: value
        for name, value in (
            ("episodes", args.episodes), ("learning_rate", args.learning_rate),
            ("discount_factor", args.discount), ("epsilon", args.epsilon),
            ("epsilon_decay", args.epsilon_decay), ("epsilon_min", args.epsilon_min),
        )
        if value is not None
    }
    if rl_changes:
        settings = settings.with_changes("rl", **rl_changes)
    return settings


def _print_overview(settings: Settings) -> None:
    print(f"{PROJECT_NAME}  v{PROJECT_VERSION}")
    print("An academic simulation. Nothing here controls real traffic.")
    print()
    print(f"Current build: {CURRENT_PHASE}")
    print("The menu and result screens arrive in later phases.")
    print()
    traffic, sim = settings.traffic, settings.simulation
    print(f"Active settings: scenario '{traffic.scenario}', seed {traffic.seed}, "
          f"duration {sim.duration:g} s")
    print()
    print("Try:")
    print("  python main.py --train --train-scenarios all --episodes 700")
    print("  python main.py --experiment --experiment-scenarios all --runs 20")
    print("  python main.py --train --scenario rush_hour --episodes 300")
    print("  python main.py --demo --controller rl --scenario rush_hour --seed 7")
    print("  python main.py --window --controller rl")
    print("  python main.py --model-info")
    print("  python main.py --window")
    print("  python main.py --window --scenario rush_hour --speed 5")
    print("  python main.py --demo")
    print("  python main.py --demo --scenario rush_hour --duration 300 --seed 7")
    print("  python main.py --demo --ns-green 20 --ew-green 40")
    print("  python main.py --screenshot docs/images/frame.png")
    print("  python main.py --env-demo --scenario rush_hour --duration 300")
    print("  python main.py --list-scenarios")
    print("  python main.py --write-settings      (then edit config/user_settings.json)")
    print("  python -m unittest discover -s tests -t .")


def _print_scenarios() -> None:
    print("Available traffic scenarios (average arrivals per minute on each road):\n")
    for profile in SCENARIOS.values():
        rates = "  ".join(f"{name[0].upper()} {rate * 60:4.1f}" for name, rate in profile.rates.items())
        print(f"  {profile.name:<10} {rates}")
        print(f"  {'':<10} {profile.description}")


def _write_settings(path: Path, force: bool) -> int:
    if path.exists() and not force:
        print(f"{path} already exists. Use --force to replace it.")
        return 1
    Settings().save(path)
    print(f"Default settings written to {path}")
    print("Edit the file, then run the program again; it will be picked up automatically.")
    log.info("Default settings written to %s", path)
    return 0


def _model_path(args: argparse.Namespace) -> Path:
    return args.model or (MODEL_DIR / DEFAULT_MODEL_NAME)


def _build_controller(args: argparse.Namespace, settings: Settings) -> Controller:
    """The fixed-time controller, or the trained agent loaded from the model file."""
    if args.controller == "rl":
        path = _model_path(args)
        agent = QLearningAgent.load(path, settings.rl)
        log.info("Loaded model %s (%d episodes)", path, agent.episodes_trained)
        return QLearningController(agent)
    return FixedTimeController(settings)


def _parse_scenarios(text: str | None, option: str = "--train-scenarios") -> list[str] | None:
    if text is None:
        return None
    names = SCENARIO_NAMES if text.strip().lower() == "all" else [
        part.strip() for part in text.split(",") if part.strip()]
    unknown = [n for n in names if n not in SCENARIO_NAMES]
    if unknown or not names:
        raise ConfigError([f"{option}: unknown scenario(s) {', '.join(unknown) or text!r}; "
                           f"use 'all' or a comma separated list of: {', '.join(SCENARIO_NAMES)}."])
    return list(names)


def _experiment(args: argparse.Namespace, settings: Settings) -> int:
    scenarios = _parse_scenarios(args.experiment_scenarios, "--experiment-scenarios")
    if not 1 <= args.runs <= MAX_RUNS:
        raise ConfigError([f"--runs must be between 1 and {MAX_RUNS}."])
    agent = None
    if not args.no_rl:
        path = _model_path(args)
        if not path.exists() and args.model is None:
            print(f"No trained model found at {path}.\n"
                  "Train one first:  python main.py --train --train-scenarios all\n"
                  "or compare only the fixed-time controllers:  python main.py --experiment --no-rl")
            return 1
        agent = QLearningAgent.load(path, settings.rl)
    names = scenarios or [settings.traffic.scenario]
    print(f"Experiment: {len(names)} scenario(s), {args.runs} runs per controller, "
          f"{settings.simulation.duration:g} s each, base seed {settings.traffic.seed}")
    if agent is not None:
        trained = agent.info.get("training", {}).get("scenarios")
        print(f"Q-Learning model: {agent.episodes_trained} training episodes"
              + (f", trained on {', '.join(trained)}" if trained else ""))
        if trained and not set(names) <= set(trained):
            print("Note: some tested scenarios were not in the training; the agent is tested on traffic "
                  "types it has not practised.")
    print("(tuning the fixed-time controller and running every controller takes a little while)\n")

    seen = {"scenario": None}

    def progress(done: int, total: int, text: str) -> None:
        scenario = text.split(":")[0]
        if scenario != seen["scenario"]:
            seen["scenario"] = scenario
            print(f"  running {scenario} ... ({done}/{total} runs done)", flush=True)

    result = run_experiment(settings, names, runs=args.runs, agent=agent, tune=not args.no_tune,
                            on_progress=progress)
    print()
    print("\n".join(format_experiment(result)))
    graphs = not args.no_graphs
    try:
        folder = save_experiment(result, args.results_dir or RESULTS_DIR, graphs=graphs)
    except ImportError:
        print("matplotlib is not installed, so no graphs were drawn "
              "(pip install -r requirements.txt). Saving the other files...")
        folder = save_experiment(result, args.results_dir or RESULTS_DIR, graphs=False)
    print(f"Results saved in {folder}")
    print("  summary.md (report), runs.csv, summary.csv, comparison.csv, experiment.json"
          + (", graphs/" if graphs and (folder / 'graphs').exists() else ""))
    log.info("Experiment finished: %s", folder)
    unsafe = sum(s.safety_violations() for s in result.scenarios)
    return 0 if unsafe == 0 else 1


def _train(args: argparse.Namespace, settings: Settings) -> int:
    path = _model_path(args)
    scenarios = _parse_scenarios(args.train_scenarios)
    if path.exists() and not (args.force or args.continue_training):
        print(f"{path} already exists. Use --continue-training to keep training it, "
              "or --force to replace it, or --model FILE to use another file.")
        return 1
    agent = (QLearningAgent.load(path, settings.rl, seed=settings.traffic.seed)
             if args.continue_training and path.exists()
             else QLearningAgent(settings.rl, seed=settings.traffic.seed))
    trainer = Trainer(settings, agent, scenarios)
    total = settings.rl.episodes
    rl = settings.rl
    stamp = f"{datetime.now():%Y%m%d_%H%M%S}"
    log_path = None if args.no_log else CSV_DIR / f"training_{stamp}.csv"

    print("Training the Q-Learning agent (this does not open a window; Ctrl+C stops safely)")
    print(f"Episodes {total}, each {settings.simulation.duration:g} s of simulated traffic; "
          f"scenario(s): {', '.join(trainer.scenarios)}")
    print(f"learning rate {rl.learning_rate:g}, discount {rl.discount_factor:g}, epsilon "
          f"{agent.epsilon:.3g} -> {rl.epsilon_min:g} (x{rl.epsilon_decay:g} per episode), "
          f"base seed {settings.traffic.seed}")
    print()
    print("  episode  epsilon  avg reward  avg queue  avg wait (s)")
    every = max(1, total // 20)
    window = max(1, every)
    history: list = []

    def progress(stats, expected) -> None:
        history.append(stats)
        if stats.episode % every == 0 or len(history) == expected:
            recent = history[-window:]
            reward = rolling_mean([h.total_reward for h in recent], len(recent))[-1]
            queue = rolling_mean([h.average_queue_length for h in recent], len(recent))[-1]
            wait = rolling_mean([h.average_waiting_time for h in recent], len(recent))[-1]
            print(f"  {stats.episode:>7}  {stats.epsilon:>7.3f}  {reward:>10.1f}  "
                  f"{queue if queue is not None else float('nan'):>9.1f}  "
                  f"{wait if wait is not None else float('nan'):>12.1f}")

    interrupted = False
    result = None
    try:
        result = trainer.train(total, on_episode=progress, log_path=log_path)
    except KeyboardInterrupt:
        interrupted = True
        print("\nStopping; saving what was learned so far...")
    done = result.episodes_done if result else len(history)
    unsafe = sum(h.safety_violations for h in history)
    info = {"scenarios": trainer.scenarios, "base_seed": settings.traffic.seed,
            "episode_seconds": settings.simulation.duration,
            "stopped_early": interrupted or bool(result and result.stopped_early),
            "best_episode": result.best_episode if result else None,
            "best_validation_waiting_time": result.best_score if result else None,
            "validation_runs": settings.rl.validation_runs if result else None}
    saved = agent.save(path, **info)
    print()
    print(f"Trained {done} episode(s) in {result.seconds:.1f} s; " if result else
          f"Trained {done} episode(s); ", end="")
    print(f"safety conflicts during training: {unsafe} ({'PASSED' if unsafe == 0 else 'FAILED'})")
    if result and result.best_episode is not None:
        print(f"Kept the best policy found: episode {result.best_episode} "
              f"(validation average wait {result.best_score:.1f} s)")
    print(f"Model saved to {saved}")
    if log_path is not None:
        print(f"Episode log: {log_path}")
    if not args.no_graphs and len(history) >= 2:
        try:
            from evaluation.graphs import save_training_graphs
            files = save_training_graphs(history, GRAPH_DIR, stamp)
            print("Training graphs: " + ", ".join(str(f) for f in files))
        except ImportError:
            print("(matplotlib is not installed, so no training graphs were drawn.)")
    print("Try it:  python main.py --demo --controller rl")
    log.info("Training finished: %d episodes, model %s", done, saved)
    return 130 if interrupted else (0 if unsafe == 0 else 1)


def _show_model_info(args: argparse.Namespace, settings: Settings) -> int:
    path = _model_path(args)
    agent = QLearningAgent.load(path, settings.rl)
    info = agent.info
    training, params = info.get("training", {}), info.get("parameters", {})
    print(f"Model file : {path}")
    print(f"Saved      : {info.get('saved_at', 'unknown')}   (format version {info.get('version')})")
    print(f"Trained    : {agent.episodes_trained} episodes, {agent.updates} updates, "
          f"final epsilon {agent.epsilon:.3f}")
    if training.get("scenarios"):
        print(f"Scenarios  : {', '.join(training['scenarios'])}   base seed {training.get('base_seed')}")
    if training.get("best_episode") is not None:
        print(f"Best policy: episode {training['best_episode']} "
              f"(validation average wait {training.get('best_validation_waiting_time'):.1f} s)")
    print("Parameters : " + ", ".join(f"{k} {v:g}" for k, v in params.items()))
    print()
    print("What it learned (best action in each state; Q-values are expected future reward):")
    print(f"  {'state':<48} {'KEEP':>8} {'SWITCH':>8} {'visits':>8}  best")
    for row in agent.policy_table():
        visits = row["visits_keep"] + row["visits_switch"]
        print(f"  {row['description']:<48} {row['q_keep']:>8.1f} {row['q_switch']:>8.1f} "
              f"{visits:>8}  {row['best']}")
    return 0


def _load_ui():
    """Import the window code only when it is needed; None if pygame is missing."""
    try:
        from ui import simulation_screen
    except ImportError:
        log.exception("pygame could not be imported")
        return None
    return simulation_screen


def _run_visual(args: argparse.Namespace, settings: Settings) -> int:
    if args.screenshot is not None and args.screenshot.suffix.lower() != ".png":
        raise ConfigError(["--screenshot file name must end in .png"])
    if args.screenshot_at < 0:
        raise ConfigError(["--screenshot-at must not be negative."])
    ui = _load_ui()
    if ui is None:
        print(PYGAME_MISSING_MESSAGE, file=sys.stderr)
        return 1
    controller = _build_controller(args, settings)
    if args.screenshot is not None:
        path = ui.save_screenshot(args.screenshot, settings, controller,
                                  after_seconds=args.screenshot_at)
        print(f"Screenshot saved to {path}")
        return 0
    log.info("Window started: scenario=%s seed=%s", settings.traffic.scenario, settings.traffic.seed)
    ui.run_window(settings, controller, speed=args.speed, paused=args.paused)
    return 0


def _dispatch(args: argparse.Namespace) -> int:
    if args.list_scenarios:
        _print_scenarios()
        return 0
    if args.write_settings:
        return _write_settings(args.config or SETTINGS_FILE, args.force)

    settings = _apply_overrides(_load_settings(args.config), args)
    if args.demo:
        if args.report_every <= 0:
            raise ConfigError(["--report-every must be greater than 0."])
        log.info("Demo started: scenario=%s seed=%s duration=%s",
                 settings.traffic.scenario, settings.traffic.seed, settings.simulation.duration)
        result = run_demo(settings, _build_controller(args, settings),
                          report_every=args.report_every)
        log.info("Demo finished: %s", result.simulator.summary())
        return 0 if result.metrics.safety_violations == 0 else 1
    if args.experiment:
        return _experiment(args, settings)
    if args.model_info:
        return _show_model_info(args, settings)
    if args.train:
        return _train(args, settings)
    if args.env_demo:
        if not 1 <= args.env_episodes <= 1000:
            raise ConfigError(["--env-episodes must be between 1 and 1000."])
        result = run_env_demo(settings, episodes=args.env_episodes)
        return 0 if result.safety_violations == 0 else 1
    if args.window or args.screenshot is not None:
        return _run_visual(args, settings)
    _print_overview(settings)
    return 0


def main(argv: list[str] | None = None) -> int:
    _configure_console()
    args = build_parser().parse_args(argv)
    try:
        ensure_directories()
        # Technical details go to the log file only; the console shows friendly text.
        if setup_logging(LOG_DIR, console_level=logging.CRITICAL) is None:
            print(f"Note: the log file in {LOG_DIR} could not be opened; "
                  "continuing without logging.", file=sys.stderr)
        log.info("%s v%s started", PROJECT_NAME, PROJECT_VERSION)
        return _dispatch(args)
    except ConfigError as exc:
        log.error("Settings problem: %s", "; ".join(exc.problems))
        print("There is a problem with the settings:", file=sys.stderr)
        for problem in exc.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 2
    except ModelError as exc:
        log.error("Model problem: %s", exc)
        print(f"There is a problem with the model: {exc}", file=sys.stderr)
        return 2
    except BrokenPipeError:
        # The reader closed the pipe (for example `... | head`); not an error.
        # Point stdout at nowhere so Python does not complain again while exiting.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 0
    except OSError as exc:
        log.exception("File problem")
        print(f"A file or folder could not be used: {exc.strerror or exc}.", file=sys.stderr)
        print(f"Details were written to {LOG_DIR / 'application.log'}.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopped by user.")
        return 130
    except Exception:  # noqa: BLE001 - last line of defence: log it, show a friendly message
        log.exception("Unexpected error")
        print("Something unexpected went wrong.", file=sys.stderr)
        print(f"Technical details were written to {LOG_DIR / 'application.log'}.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
