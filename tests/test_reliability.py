"""Phase 9: bad input, damaged files, file-system errors and window failures must never crash the program."""

import contextlib
import copy
import io
import json
import os
import random
import tempfile
import time
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("MPLBACKEND", "Agg")

import main
from agents.q_learning import ModelError, QLearningAgent
from config.settings import MAX_STEPS_PER_RUN, ConfigError, Settings
from controllers.fixed_controller import FixedTimeController
from controllers.rl_controller import QLearningController
from simulation.runner import run_episode
from tests.test_experiment import settings_for, varied_agent
from utils.logging_setup import teardown_logging

WEIRD = [float("nan"), float("inf"), -float("inf"), None, True, "5", [], {}, 0, -1, 1e308, 1e-308, 10**30, 0.0, 2**63]


class SettingsRobustnessTests(unittest.TestCase):
    def test_no_value_in_any_field_can_crash_or_hang_the_simulation(self):
        base = asdict(Settings())
        started = time.time()
        for section, values in base.items():
            for name in values:
                for weird in WEIRD:
                    data = {s: dict(v) for s, v in base.items()}
                    data[section][name] = weird
                    try:
                        settings = Settings.from_dict(data)
                    except ConfigError:
                        continue
                    short = settings.with_changes("simulation", duration=min(settings.simulation.duration, 20.0))
                    run_episode(short, FixedTimeController(short), seed=1)  # accepted values must be usable
        self.assertLess(time.time() - started, 60)

    def test_tiny_time_steps_and_endless_runs_are_refused(self):
        for changes in ({"dt": 1e-308}, {"dt": 0.001}, {"dt": 0.0}, {"duration": 86_400.0, "dt": 0.01},
                        {"acceleration": 0.001}, {"braking": 0.0}, {"halting_speed": 1e-9}):
            with self.assertRaises(ConfigError, msg=changes):
                Settings().with_changes("simulation", **changes)
        Settings().with_changes("simulation", dt=0.01, duration=600.0)  # the smallest allowed step is fine
        self.assertGreater(86_400 / 0.01, MAX_STEPS_PER_RUN)

    def test_structurally_wrong_settings_are_reported_not_raised(self):
        cases = [None, 1, "x", [], [1], {"simulation": None}, {"simulation": []}, {"simulation": {"dt": {"a": 1}}},
                 {"traffic": {"scenario": ["low"]}}, {"traffic": {"weights": None}}, {"rl": {"episodes": 1e18}},
                 {"rl": {"episodes": 2.5}}, {"display": {"theme": None}}, {"display": {"window_width": -5}}, {"": 1}]
        for case in cases:
            with self.assertRaises(ConfigError, msg=case):
                Settings.from_dict(case)

    def test_garbage_settings_files_give_a_friendly_error(self):
        garbage = {"binary": os.urandom(3000), "empty": b"", "nan": b'{"simulation":{"duration":NaN}}',
                   "deep": b"[" * 100_000, "huge number": b'{"a":' + b"1" * 5000 + b"}",
                   "too big": b" " * 2_000_000, "not utf8": b"\xff\xfe\x00{"}
        with tempfile.TemporaryDirectory() as tmp:
            for name, data in garbage.items():
                path = Path(tmp) / name
                path.write_bytes(data)
                with self.assertRaises(ConfigError, msg=name) as caught:
                    Settings.load(path)
                self.assertTrue(caught.exception.problems, name)
            Settings.load  # directories too
            with self.assertRaises(ConfigError):
                Settings.load(tmp)


class ModelRobustnessTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.settings = settings_for(40.0, "low", 1)
        self.good = self.dir / "good.json"
        varied_agent(self.settings).save(self.good, scenarios=["low"], base_seed=1, best_episode=3,
                                         best_validation_waiting_time=7.5)
        self.data = json.loads(self.good.read_text(encoding="utf-8"))

    def paths(self, obj, prefix=()):
        if isinstance(obj, dict):
            for key, value in obj.items():
                yield from self.paths(value, prefix + (key,))
        elif isinstance(obj, list):
            yield prefix
            for i, value in enumerate(obj[:2]):
                yield from self.paths(value, prefix + (i,))
        else:
            yield prefix

    def test_every_damaged_value_is_refused_or_harmless(self):
        target = self.dir / "m.json"
        weird = [float("nan"), float("inf"), -1e308, None, True, "x", [], {}, -1, 10**30, [1, 2, 3], [[]]]
        accepted = 0
        for path in sorted(set(self.paths(self.data)), key=str):
            if not path:
                continue
            for value in weird:
                mutated = copy.deepcopy(self.data)
                node = mutated
                for key in path[:-1]:
                    node = node[key]
                node[path[-1]] = value
                target.write_text(json.dumps(mutated), encoding="utf-8")
                try:
                    agent = QLearningAgent.load(target, self.settings.rl)
                except ModelError:
                    continue
                accepted += 1  # anything accepted must also be usable and describable
                run_episode(self.settings, QLearningController(agent), seed=1)
                info = agent.info.get("training", {})
                format(info.get("best_validation_waiting_time") or 0.0, ".1f")
                for key, number in agent.info.get("parameters", {}).items():
                    format(number, "g")
        self.assertGreater(accepted, 0)

    def test_garbage_model_files(self):
        target = self.dir / "x.json"
        for name, data in {"binary": os.urandom(3000), "empty": b"", "deep": b"[" * 100_000,
                           "too big": b" " * 6_000_000, "nan": b'{"format": NaN}'}.items():
            target.write_bytes(data)
            with self.assertRaises(ModelError, msg=name):
                QLearningAgent.load(target, self.settings.rl)
        with self.assertRaises(ModelError):
            QLearningAgent.load(self.dir, self.settings.rl)  # a folder


class CommandLineRobustnessTests(unittest.TestCase):
    CASES = [
        ["--demo", "--duration", "nan"], ["--demo", "--duration", "inf"], ["--demo", "--duration", "-5"],
        ["--demo", "--duration", "1e12"], ["--demo", "--seed", "-1"], ["--demo", "--seed", "99999999999999"],
        ["--demo", "--seed", "abc"], ["--demo", "--ns-green", "nan"], ["--demo", "--ns-green", "1e9"],
        ["--demo", "--report-every", "0"], ["--demo", "--report-every", "nan"],
        ["--train", "--episodes", "0"], ["--train", "--episodes", "-3"], ["--train", "--episodes", "99999999999999999999"],
        ["--train", "--train-scenarios", ""], ["--train", "--train-scenarios", ",,"], ["--train", "--train-scenarios", "low,nope"],
        ["--demo", "--controller", "rl", "--model", "/dev/null"], ["--demo", "--controller", "rl", "--model", "/etc/passwd"],
        ["--model-info", "--model", "/nonexistent.json"], ["--model-info", "--model", "/tmp"],
        ["--experiment", "--runs", "0", "--no-rl"], ["--experiment", "--runs", "nan", "--no-rl"],
        ["--experiment", "--runs", "5.5", "--no-rl"],
        ["--screenshot", "x.txt"], ["--screenshot", "/tmp/x.png", "--screenshot-at", "-1"],
        ["--window", "--speed", "3"], ["--window", "--speed", "nan"], ["--menu", "--screen", "nope"],
        ["--config", "/nonexistent.json", "--demo"], ["--config", "/tmp", "--demo"], ["--config", "/dev/null", "--demo"],
        ["--env-demo", "--env-episodes", "0"], ["--env-demo", "--env-episodes", "nan"], ["--unknown"],
    ]

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.addCleanup(teardown_logging)
        self.dir = Path(tmp.name)
        for name, value in (("LOG_DIR", self.dir / "logs"), ("MODEL_DIR", self.dir / "models"),
                            ("CSV_DIR", self.dir / "csv"), ("GRAPH_DIR", self.dir / "graphs"),
                            ("RESULTS_DIR", self.dir / "results"), ("SETTINGS_FILE", self.dir / "s.json")):
            patcher = mock.patch.object(main, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_bad_arguments_never_show_a_traceback(self):
        for args in self.CASES:
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try:
                    code = main.main(list(args))
                except SystemExit as exc:  # argparse's own usage errors
                    code = exc.code
            self.assertIn(code, (0, 1, 2), args)
            self.assertNotIn("Traceback", err.getvalue() + out.getvalue(), args)
            self.assertNotIn("unexpected", err.getvalue(), args)


class FileSystemFailureTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.blocker = self.dir / "blocker"
        self.blocker.write_text("a file where a folder should be", encoding="utf-8")
        self.settings = settings_for(40.0, "low", 3, validation_every=0)

    def test_a_graph_failure_never_loses_the_saved_model(self):
        from training.workflow import TrainingPlan, run_training
        plan = TrainingPlan(self.settings, ["low"], 3, self.dir / "m.json")
        with mock.patch("evaluation.graphs.save_training_graphs", side_effect=RuntimeError("boom")), \
                self.assertLogs("training.workflow", level="ERROR"):
            out = run_training(plan, self.dir / "c", self.dir / "g")
        self.assertTrue(out.saved and out.model_path.is_file())
        self.assertIn("model was saved", out.graph_note)

    def test_a_graph_failure_never_loses_a_finished_experiment(self):
        from evaluation.experiment import run_experiment
        from evaluation.export import save_experiment
        result = run_experiment(self.settings, ["low"], runs=2, agent=None, tune=False)
        with mock.patch("evaluation.graphs.save_experiment_graphs", side_effect=RuntimeError("boom")), \
                self.assertLogs("evaluation.export", level="ERROR"):
            folder = save_experiment(result, self.dir / "r", graphs=True)
        for name in ("summary.md", "runs.csv", "summary.csv", "comparison.csv", "experiment.json"):
            self.assertTrue((folder / name).is_file(), name)

    def test_file_errors_in_a_job_are_plain_english(self):
        from ui.jobs import BackgroundJob

        def work(job):
            (self.blocker / "x").mkdir()
        job = BackgroundJob("t", work)
        with self.assertLogs("ui.jobs", level="ERROR"):
            job.start()
            job.wait(5)
        self.assertEqual(job.state, "failed")
        self.assertTrue(job.error.startswith("A file or folder could not be used"))
        self.assertNotIn("Errno", job.error)

    def test_a_blocked_training_folder_fails_before_any_work_is_lost(self):
        from training.workflow import TrainingPlan, run_training
        for kwargs in ({"model_path": self.blocker / "m.json"},):
            plan = TrainingPlan(self.settings, ["low"], 2, **{"model_path": self.dir / "m.json", **kwargs})
            with self.assertRaises(OSError):
                run_training(plan, self.dir / "c", self.dir / "g")
        plan = TrainingPlan(self.settings, ["low"], 2, self.dir / "m.json")
        with self.assertRaises(OSError):
            run_training(plan, self.blocker / "c", self.dir / "g")

    def test_unwritable_settings_file_is_reported(self):
        with self.assertRaises(ConfigError) as caught:
            Settings().save(self.blocker / "s.json")
        self.assertIn("Could not save", caught.exception.problems[0])


try:
    import pygame
except ImportError:  # pragma: no cover
    pygame = None


@unittest.skipIf(pygame is None, "pygame is not installed")
class WindowRobustnessTests(unittest.TestCase):
    def setUp(self):
        from ui.app import App, AppPaths
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.settings = Settings().updated(simulation={"duration": 40.0}, rl={"validation_every": 0})
        self.paths = AppPaths(self.dir / "m" / "model.json", self.dir / "c", self.dir / "g",
                              self.dir / "r", self.dir / "s.json")
        (self.dir / "m").mkdir()
        varied_agent(self.settings).save(self.paths.model_path, scenarios=["rush_hour"])
        self.App = App

    def test_tiny_windows_are_raised_to_the_minimum(self):
        from ui.app import MIN_WINDOW
        app = self.App(self.settings, self.paths, size=(1, 1))
        self.assertEqual(app.size, MIN_WINDOW)
        app.resize((50, 50))
        self.assertEqual(app.size, MIN_WINDOW)
        app.handle_event(pygame.event.Event(pygame.VIDEORESIZE, w=10, h=10, size=(10, 10)))
        self.assertEqual(app.size, MIN_WINDOW)
        for name in ("menu", "compare", "watch_fixed", "training", "experiment", "results", "settings", "about"):
            app.go(name)
            app.update(0.1)
            app.draw(pygame.Surface(app.size))

    def test_an_error_inside_a_screen_returns_to_the_menu(self):
        app = self.App(self.settings, self.paths, size=(1280, 720))
        app.go("about")
        with mock.patch.object(type(app.screen), "draw_content", side_effect=RuntimeError("bug")), \
                self.assertLogs("ui.app", level="ERROR"):
            app.draw(pygame.Surface(app.size))
        self.assertEqual(app.screen.name, "menu")
        self.assertIn("Something went wrong", app.toast[0])
        self.assertFalse(app.quit_requested)
        app.draw(pygame.Surface(app.size))  # and it keeps working
        self.assertEqual(app.failures, 0)

    def test_a_screen_that_always_fails_ends_the_program_politely(self):
        app = self.App(self.settings, self.paths, size=(1280, 720))
        app.go("menu")
        with mock.patch.object(type(app.screen), "draw_content", side_effect=RuntimeError("bug")), \
                self.assertLogs("ui.app", level="ERROR"):
            for _ in range(10):
                app.draw(pygame.Surface(app.size))
        self.assertTrue(app.quit_requested)
        self.assertIn("logs/application.log", app.fatal_message)

    def test_an_error_in_an_event_handler_or_update_is_contained_too(self):
        app = self.App(self.settings, self.paths, size=(1280, 720))
        app.go("settings")
        with mock.patch.object(type(app.screen), "on_click", side_effect=RuntimeError("bug")), \
                self.assertLogs("ui.app", level="ERROR"):
            app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(5, 5)))
        self.assertEqual(app.screen.name, "menu")
        with mock.patch.object(type(app.screen), "update", side_effect=ValueError("bug")), \
                self.assertLogs("ui.app", level="ERROR"):
            app.update(0.1)

    def test_leaving_a_screen_stops_its_background_job(self):
        app = self.App(self.settings, self.paths, size=(1280, 720))
        screen = app.go("training")
        screen.episodes.set_value(5000)
        screen.begin()
        if screen.dialog is not None:  # a model already exists: confirm the replacement
            app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=screen.dialog.buttons[0].rect.center))
        deadline = time.time() + 30
        while not screen.history and time.time() < deadline:
            time.sleep(0.05)
        job = screen.job
        self.assertTrue(job.active)
        app.go("menu")  # e.g. after an unexpected error
        self.assertTrue(job.wait(30))
        self.assertTrue(job.finished)

    def test_random_input_sessions_never_raise(self):
        from ui.screens import SCREENS
        errors = []

        class Collect(__import__("logging").Handler):
            def emit(self, record):
                if record.levelno >= 40:
                    errors.append(record.getMessage())
        handler = Collect()
        import logging
        logging.getLogger("ui").addHandler(handler)
        self.addCleanup(logging.getLogger("ui").removeHandler, handler)
        keys = [pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE, pygame.K_BACKSPACE, pygame.K_UP, pygame.K_DOWN,
                pygame.K_LEFT, pygame.K_RIGHT, pygame.K_q, pygame.K_s, pygame.K_r, pygame.K_n, pygame.K_h,
                pygame.K_DELETE] + list(range(48, 58)) + list(range(97, 123))
        for seed in range(6):
            rng = random.Random(seed)
            sub = self.dir / f"s{seed}"
            sub.mkdir()
            from ui.app import AppPaths
            paths = AppPaths(sub / "model.json", sub / "c", sub / "g", sub / "r", sub / "s.json")
            if seed % 2:
                varied_agent(self.settings).save(paths.model_path)
            size = rng.choice([(1280, 720), (800, 600), (640, 480), (100, 100), (3000, 2000)])
            app = self.App(self.settings, paths, size=size)
            for _ in range(250):
                if app.screen is None or rng.random() < 0.04:
                    app.go(rng.choice(list(SCREENS)))
                roll = rng.random()
                if roll < 0.4:
                    k = rng.choice(keys)
                    event = pygame.event.Event(pygame.KEYDOWN, key=k, unicode=chr(k) if 32 <= k < 127 else "")
                elif roll < 0.85:
                    event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=rng.choice([1, 1, 2, 3]),
                                               pos=(rng.randint(-50, size[0] + 50), rng.randint(-50, size[1] + 50)))
                elif roll < 0.95:
                    size = (rng.choice([1, 200, 700, 2500]), rng.choice([1, 200, 500, 1500]))
                    event = pygame.event.Event(pygame.VIDEORESIZE, w=size[0], h=size[1], size=size)
                else:
                    event = pygame.event.Event(pygame.MOUSEMOTION, pos=(5, 5), rel=(0, 0), buttons=(0, 0, 0))
                app.handle_event(event)
                app.quit_requested = False
                app.update(rng.choice([0.0, 0.016, 0.5]))
                app.draw(pygame.Surface(app.size))
            job = getattr(app.screen, "job", None)
            if job is not None and job.active:
                job.request_stop()
                job.wait(30)
        self.assertEqual(errors, [])


@unittest.skipIf(pygame is None, "pygame is not installed")
class DeleteConfirmationTests(unittest.TestCase):
    def setUp(self):
        from evaluation.experiment import run_experiment
        from evaluation.export import save_experiment
        from ui.app import App, AppPaths
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.settings = settings_for(40.0, "low", 3, validation_every=0)
        self.paths = AppPaths(self.dir / "m" / "model.json", self.dir / "c", self.dir / "g",
                              self.dir / "r", self.dir / "s.json")
        (self.dir / "m").mkdir()
        varied_agent(self.settings).save(self.paths.model_path)
        result = run_experiment(self.settings, ["low"], runs=1, agent=None, tune=False)
        self.folder = save_experiment(result, self.paths.results_dir, graphs=False)
        self.app = App(self.settings, self.paths, size=(1280, 720))

    def click(self, button):
        self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=button.rect.center))

    def open(self, name):
        screen = self.app.go(name)
        self.app.draw(pygame.Surface(self.app.size))
        return screen

    def test_deleting_an_experiment_asks_first(self):
        screen = self.open("results")
        self.click(screen.delete_button)
        self.assertIsNotNone(screen.dialog)
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode=""))  # Keep it
        self.assertTrue(self.folder.is_dir())
        self.click(screen.delete_button)
        self.click(screen.dialog.buttons[0])
        self.assertFalse(self.folder.exists())
        self.assertEqual(screen.items, [])
        self.assertFalse(screen.delete_button.enabled)

    def test_delete_refuses_anything_that_is_not_an_experiment_folder_inside_results(self):
        screen = self.open("results")
        other = self.paths.results_dir / "important"
        other.mkdir()
        screen.items = [("x", other, "")]
        screen.delete_selected()
        self.assertTrue(other.is_dir())
        screen.items = [("x", self.dir / "m", "")]  # outside the results folder (path name only is used)
        screen.delete_selected()
        self.assertTrue((self.dir / "m").is_dir())
        self.assertEqual(self.app.toast[1], "warning")

    def test_deleting_a_training_graph(self):
        self.paths.graph_dir.mkdir(parents=True)
        graph = self.paths.graph_dir / "training_x_reward.png"
        graph.write_bytes(b"x")
        keep = self.paths.graph_dir / "notes.txt"
        keep.write_text("keep", encoding="utf-8")
        screen = self.open("results")
        self.click(screen.mode_buttons[1])
        self.assertEqual(len(screen.items), 1)
        self.click(screen.delete_button)
        self.click(screen.dialog.buttons[0])
        self.assertFalse(graph.exists())
        self.assertTrue(keep.exists())

    def test_deleting_the_model_asks_first_and_updates_the_app(self):
        screen = self.open("training")
        self.assertEqual(self.app.model_status()[0], "ok")
        self.click(screen.delete_model)
        self.assertIsNotNone(screen.dialog)
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode=""))
        self.assertTrue(self.paths.model_path.exists())
        self.click(screen.delete_model)
        self.click(screen.dialog.buttons[0])
        self.assertFalse(self.paths.model_path.exists())
        self.assertEqual(self.app.model_status()[0], "none")
        self.assertFalse(screen.delete_model.enabled)
        self.assertFalse(screen.mode.enabled)

    def test_nothing_is_deleted_while_training_runs(self):
        screen = self.open("training")
        screen.episodes.set_value(5000)
        screen.begin()
        if screen.dialog is not None:
            self.click(screen.dialog.buttons[0])
        try:
            self.assertFalse(screen.delete_model.enabled)
        finally:
            screen.job.request_stop()
            screen.job.wait(30)


if __name__ == "__main__":
    unittest.main()
