"""Tests of the application window: every screen and every button, run without a display."""

import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("MPLBACKEND", "Agg")

try:
    import pygame
except ImportError:  # pragma: no cover
    pygame = None

from config.settings import Settings
from evaluation.experiment import run_experiment
from evaluation.export import save_experiment
from tests.test_experiment import varied_agent

if pygame is not None:
    from ui.app import App, AppPaths, render_screen
    from ui.screens import SCREENS
    from ui.screens.results import ResultsScreen


def settings_small(**extra):
    changes = {"simulation": {"duration": 60.0}, "traffic": {"scenario": "rush_hour", "seed": 3},
               "rl": {"validation_every": 0}}
    for k, v in extra.items():
        changes.setdefault(k, {}).update(v)
    return Settings().updated(**changes)


def key(k, char=""):
    return pygame.event.Event(pygame.KEYDOWN, key=k, unicode=char)


def click(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)


def wait_until(predicate, app, timeout=60.0):
    end = time.time() + timeout
    while time.time() < end:
        app.update(0.05)
        if predicate():
            return True
        time.sleep(0.02)
    return False


@unittest.skipIf(pygame is None, "pygame is not installed")
class AppTestCase(unittest.TestCase):
    with_model = True
    size = (1280, 720)

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.paths = AppPaths(self.dir / "models" / "model.json", self.dir / "csv", self.dir / "graphs",
                              self.dir / "results", self.dir / "settings.json")
        self.settings = settings_small()
        if self.with_model:
            self.paths.model_path.parent.mkdir(parents=True)
            varied_agent(self.settings).save(self.paths.model_path, scenarios=["rush_hour"], base_seed=3)
        self.app = App(self.settings, self.paths, size=self.size)
        self.addCleanup(self.stop_jobs)

    def stop_jobs(self):
        screen = self.app.screen
        job = getattr(screen, "job", None)
        if job is not None and job.active:
            job.request_stop()
            job.wait(60)

    def open(self, name, **kw):
        screen = self.app.go(name, **kw)
        self.app.update(0.0)
        surface = pygame.Surface(self.app.size)
        self.app.draw(surface)  # draws once so the layout exists
        return screen

    def press(self, k, char=""):
        self.app.handle_event(key(k, char))

    def type_text(self, text):
        for ch in text:
            self.press(ord(ch) if ch.isalnum() else pygame.K_PERIOD, ch)

    def click_button(self, label_or_button):
        screen = self.app.screen
        button = label_or_button
        if isinstance(label_or_button, str):
            matches = [b for b in screen.buttons if b.label == label_or_button]
            self.assertTrue(matches, f"no button {label_or_button!r} on {screen.name}")
            button = matches[0]
        self.app.handle_event(click(button.rect.center))
        return button

    def draw(self):
        surface = pygame.Surface(self.app.size)
        self.app.draw(surface)
        return surface


class MenuTests(AppTestCase):
    def test_every_button_is_visible_inside_the_window_and_leads_somewhere(self):
        expected = {"Watch fixed-time light": "watch", "Watch Q-Learning agent": "watch", "Compare side by side": "compare",
                    "Train the agent": "training", "Run an experiment": "experiment", "View results": "results",
                    "Settings": "settings", "About": "about"}
        window = pygame.Rect(0, 0, *self.size)
        for label, name in expected.items():
            menu = self.open("menu")
            for b in menu.buttons:
                self.assertTrue(window.contains(b.rect), b.label)
                self.assertGreater(b.rect.height, 30)
            self.click_button(label)
            self.assertEqual(self.app.screen.name, name, label)
        self.open("menu")
        self.click_button("Quit")
        self.assertTrue(self.app.quit_requested)

    def test_number_keys_open_the_same_screens(self):
        for k, name in ((pygame.K_1, "watch"), (pygame.K_3, "compare"), (pygame.K_4, "training"),
                        (pygame.K_5, "experiment"), (pygame.K_6, "results"), (pygame.K_7, "settings"),
                        (pygame.K_8, "about")):
            self.open("menu")
            self.press(k)
            self.assertEqual(self.app.screen.name, name)
        self.open("menu")
        self.press(pygame.K_q)
        self.assertTrue(self.app.quit_requested)

    def test_closing_the_window_quits(self):
        self.open("menu")
        self.app.handle_event(pygame.event.Event(pygame.QUIT))
        self.assertTrue(self.app.quit_requested)

    def test_shows_the_current_setup_and_model(self):
        self.open("menu")
        self.assertEqual(self.app.model_status()[0], "ok")
        self.assertIn("trained 7 episodes", self.app.model_status()[1])

    def test_screens_can_be_rebuilt_many_times(self):
        for _ in range(5):
            for name in ("menu", "about", "settings", "results", "training", "experiment"):
                self.open(name)
                self.press(pygame.K_ESCAPE)


class MenuWithoutModelTests(AppTestCase):
    with_model = False

    def test_model_dependent_buttons_are_disabled_and_explain_why(self):
        menu = self.open("menu")
        self.assertEqual(self.app.model_status()[0], "none")
        for label in ("Watch Q-Learning agent", "Compare side by side"):
            button = next(b for b in menu.buttons if b.label == label)
            self.assertFalse(button.enabled)
            self.click_button(button)
            self.assertEqual(self.app.screen.name, "menu")
            self.assertIn("Train the agent", button.tooltip)
        self.assertTrue(next(b for b in menu.buttons if b.label == "Watch fixed-time light").enabled)

    def test_opening_the_agent_directly_returns_to_the_menu_with_a_message(self):
        for name in ("watch_rl", "compare"):
            self.app.go(name)
            self.assertEqual(self.app.screen.name, "menu")
            self.assertIn("No trained model", self.app.toast[0])

    def test_damaged_model_is_reported_not_crashed(self):
        self.paths.model_path.parent.mkdir(parents=True)
        self.paths.model_path.write_text("{broken", encoding="utf-8")
        status, text = self.app.model_status()
        self.assertEqual(status, "bad")
        self.assertIn("cannot be used", text)
        menu = self.open("menu")
        self.assertFalse(next(b for b in menu.buttons if b.label == "Compare side by side").enabled)


class WatchTests(AppTestCase):
    def test_watching_fixed_time_runs_and_returns_to_the_menu(self):
        screen = self.open("watch_fixed")
        for _ in range(20):
            self.app.update(0.1)
        self.assertGreater(screen.inner.session.sim.time, 0)
        self.press(pygame.K_SPACE)
        self.assertTrue(screen.inner.session.paused)
        self.press(pygame.K_ESCAPE)
        self.assertEqual(self.app.screen.name, "menu")

    def test_menu_button_inside_the_simulation_leaves_it(self):
        screen = self.open("watch_rl")
        self.assertIn("Q-Learning", screen.inner.session.controller.describe())
        self.click_button(next(b for b in screen.inner.buttons if b.label == "Menu"))
        self.assertEqual(self.app.screen.name, "menu")

    def test_closing_the_window_while_watching_quits(self):
        self.open("watch_fixed")
        self.app.handle_event(pygame.event.Event(pygame.QUIT))
        self.assertTrue(self.app.quit_requested)


class CompareTests(AppTestCase):
    def test_both_sides_get_identical_traffic_and_stay_in_step(self):
        screen = self.open("compare")
        fixed, rl = screen.sessions
        self.assertEqual(fixed.seed, rl.seed)
        for _ in range(60):
            self.app.update(0.1)
        self.assertEqual(fixed.sim.step_count, rl.sim.step_count)
        self.assertEqual(fixed.sim.spawned, rl.sim.spawned)
        self.assertGreater(fixed.sim.spawned, 0)
        self.assertGreater(fixed.sim.time, 0)

    def test_results_equal_separate_headless_runs(self):
        from controllers.fixed_controller import FixedTimeController
        from controllers.rl_controller import QLearningController
        from simulation.runner import run_episode
        screen = self.open("compare")
        for session in screen.sessions:
            session.speed = 10.0
        while not screen.finished:
            self.app.update(0.1)
        agent = self.app.load_agent()
        for session, controller in zip(screen.sessions, (FixedTimeController(self.settings),
                                                         QLearningController(agent))):
            expected = run_episode(self.settings, controller, seed=self.settings.traffic.seed).metrics
            self.assertEqual(session.live_metrics().to_dict(), expected.to_dict())

    def test_buttons_control_both_sides(self):
        screen = self.open("compare")
        self.click_button(screen.buttons[0])  # Pause
        self.assertTrue(all(s.paused for s in screen.sessions))
        self.click_button("Step")
        self.assertEqual({s.sim.step_count for s in screen.sessions}, {1})
        self.click_button("Faster")
        self.assertEqual({s.speed for s in screen.sessions}, {2.0})
        self.click_button("Slower")
        self.click_button("Slower")
        self.assertEqual({s.speed for s in screen.sessions}, {0.5})
        self.assertFalse(next(b for b in screen.buttons if b.label == "Slower").enabled)
        self.click_button("New traffic")
        self.assertEqual({s.seed for s in screen.sessions}, {self.settings.traffic.seed + 1})
        self.assertEqual({s.sim.step_count for s in screen.sessions}, {0})
        for _ in range(3):
            screen.step()
        self.click_button("Restart")
        self.assertEqual({s.sim.step_count for s in screen.sessions}, {0})
        self.assertEqual({s.seed for s in screen.sessions}, {self.settings.traffic.seed + 1})
        self.click_button("Menu")
        self.assertEqual(self.app.screen.name, "menu")

    def test_finished_run_shows_a_verdict_and_replays(self):
        screen = self.open("compare")
        for session in screen.sessions:
            session.speed = 10.0
        while not screen.finished:
            self.app.update(0.1)
        self.draw()
        self.assertEqual(screen.buttons[0].label, "Replay")
        self.click_button(screen.buttons[0])
        self.assertFalse(screen.finished)
        self.assertEqual(screen.sessions[0].sim.step_count, 0)


class TrainingScreenTests(AppTestCase):
    with_model = False

    def set_episodes(self, text):
        screen = self.app.screen
        self.app.handle_event(click(screen.episodes._parts()[1].center))
        self.assertTrue(screen.episodes.editing)
        for _ in range(8):
            self.press(pygame.K_BACKSPACE)
        for ch in text:
            self.press(ord(ch), ch)
        self.press(pygame.K_RETURN)

    def test_train_from_the_window_saves_a_model(self):
        screen = self.open("training")
        self.set_episodes("4")
        self.assertEqual(screen.episodes.value, 4)
        self.click_button("[x] rush_hour")  # untick, then tick another
        self.assertEqual(screen.scenarios.names, [])
        self.click_button("Start training")
        self.assertIn("at least one scenario", screen.problem)
        self.assertFalse(screen.running)
        self.click_button("[ ] rush_hour")
        self.click_button("Start training")
        self.assertTrue(wait_until(lambda: screen.job.finished, self.app))
        self.assertEqual(screen.job.state, "done", screen.job.error)
        self.assertTrue(self.paths.model_path.is_file())
        self.assertEqual(len(screen.history), 4)
        self.assertIn("saved", self.app.toast[0])
        self.assertEqual(self.app.model_status()[0], "ok")
        self.draw()  # the finished view draws
        self.click_button("Watch trained agent")
        self.assertEqual(self.app.screen.name, "watch")

    def test_bad_episode_numbers_are_refused(self):
        screen = self.open("training")
        self.set_episodes("0")
        self.assertIn("between 1", screen.episodes.error)
        self.click_button("Start training")
        self.assertFalse(screen.running)
        self.assertTrue(screen.problem)
        self.app.handle_event(click(screen.episodes._parts()[1].center))
        for _ in range(8):
            self.press(pygame.K_BACKSPACE)
        self.press(pygame.K_RETURN)  # empty
        self.assertIn("type a whole number", screen.episodes.error)

    def test_existing_model_needs_confirmation_before_replacing(self):
        varied_agent(self.settings).save(self.paths.model_path) if self.paths.model_path.parent.mkdir(
            parents=True, exist_ok=True) is None else None
        before = self.paths.model_path.read_bytes()
        screen = self.open("training")
        self.set_episodes("2")
        self.click_button("Start training")
        self.assertIsNotNone(screen.dialog)
        self.press(pygame.K_ESCAPE)  # Cancel
        self.assertIsNone(screen.dialog)
        self.assertFalse(screen.running)
        self.assertEqual(self.paths.model_path.read_bytes(), before)
        self.click_button("Start training")
        self.app.handle_event(click(screen.dialog.buttons[0].rect.center))  # Replace
        self.assertTrue(wait_until(lambda: screen.job.finished, self.app))
        self.assertNotEqual(self.paths.model_path.read_bytes(), before)

    def test_continue_mode_keeps_the_saved_model_training(self):
        varied_agent(self.settings).save(self.paths.model_path) if self.paths.model_path.parent.mkdir(
            parents=True, exist_ok=True) is None else None
        screen = self.open("training")
        self.click_button("Train a new model")
        self.assertTrue(screen.continue_training)
        self.set_episodes("2")
        self.click_button("Start training")
        self.assertIsNone(screen.dialog)  # no replace question when continuing
        self.assertTrue(wait_until(lambda: screen.job.finished, self.app))
        self.assertEqual(screen.job.state, "done", screen.job.error)
        self.assertEqual(self.app.load_agent().episodes_trained, 7 + 2)

    def test_pause_stop_and_leaving_while_running(self):
        screen = self.open("training")
        self.set_episodes("5000")
        self.click_button("Start training")
        self.assertTrue(wait_until(lambda: len(screen.history) >= 2, self.app))
        for b in screen.scenarios.buttons + [screen.start]:
            self.assertFalse(b.enabled)
        self.click_button("Pause")
        self.assertEqual(screen.job.state, "paused")
        self.assertEqual(screen.pause.label, "Resume")
        time.sleep(0.4)
        frozen = len(screen.history)
        time.sleep(0.5)
        self.assertLessEqual(len(screen.history) - frozen, 1)
        self.click_button("Resume")
        self.assertTrue(wait_until(lambda: len(screen.history) > frozen + 1, self.app))
        self.draw()
        # leaving asks first; "Keep training" stays
        self.click_button("Back")
        self.assertIsNotNone(screen.dialog)
        self.press(pygame.K_ESCAPE)
        self.assertEqual(self.app.screen.name, "training")
        self.assertTrue(screen.running)
        # stop and save on the way out
        self.click_button("Back")
        self.app.handle_event(click(screen.dialog.buttons[0].rect.center))
        self.assertTrue(wait_until(lambda: self.app.screen.name == "menu", self.app, 60))
        self.assertTrue(self.paths.model_path.is_file())
        self.assertLess(self.app.load_agent().episodes_trained, 5000)

    def test_window_close_while_training_asks_first(self):
        screen = self.open("training")
        self.set_episodes("5000")
        self.click_button("Start training")
        self.assertTrue(wait_until(lambda: len(screen.history) >= 1, self.app))
        self.app.handle_event(pygame.event.Event(pygame.QUIT))
        self.assertFalse(self.app.quit_requested)
        self.assertIsNotNone(screen.dialog)
        self.app.handle_event(click(screen.dialog.buttons[0].rect.center))
        self.assertTrue(wait_until(lambda: self.app.quit_requested, self.app, 60))

    def test_stop_button_saves_what_was_learned(self):
        screen = self.open("training")
        self.set_episodes("5000")
        self.click_button("Start training")
        self.assertTrue(wait_until(lambda: len(screen.history) >= 2, self.app))
        self.click_button("Stop and save")
        self.assertTrue(wait_until(lambda: screen.job.finished, self.app, 60))
        self.assertEqual(screen.job.state, "stopped")
        self.assertTrue(screen.job.result.stopped_early)
        self.assertTrue(self.paths.model_path.is_file())

    def test_a_failure_is_shown_not_raised(self):
        varied_agent(self.settings).save(self.paths.model_path) if self.paths.model_path.parent.mkdir(
            parents=True, exist_ok=True) is None else None
        screen = self.open("training")
        self.click_button("Train a new model")
        self.paths.model_path.write_text("{broken", encoding="utf-8")  # damaged after the screen opened
        self.app._model_cache = None
        screen.continue_training = True
        screen.mode._enabled = None
        self.set_episodes("2")
        with self.assertLogs("ui.jobs", level="ERROR"):
            screen.begin()
            wait_until(lambda: screen.job is not None and screen.job.finished, self.app)
        self.assertEqual(screen.job.state, "failed")
        self.app.update(0.1)
        self.assertTrue(screen.problem)


class ExperimentScreenTests(AppTestCase):
    def test_run_save_and_view(self):
        screen = self.open("experiment")
        self.assertTrue(screen.use_rl)
        screen.runs.set_value(2)
        self.click_button("Start experiment")
        self.assertTrue(wait_until(lambda: screen.job.finished, self.app))
        self.assertEqual(screen.job.state, "done", screen.job.error)
        folder = screen.saved_folder
        self.assertTrue((folder / "summary.md").is_file())
        text = (folder / "runs.csv").read_text(encoding="utf-8")
        for name in ("fixed,", "fixed_tuned", "rl"):
            self.assertIn(name, text)
        self.draw()
        self.click_button("View results")
        results = self.app.screen
        self.assertIsInstance(results, ResultsScreen)
        self.assertEqual(results.items[results.index][1], folder)
        self.draw()

    def test_options_change_what_is_run(self):
        screen = self.open("experiment")
        self.click_button("Tuned fixed-time: on")
        self.click_button("Q-Learning agent: on")
        self.assertFalse(screen.use_tuned or screen.use_rl)
        screen.runs.set_value(1)
        self.click_button("Start experiment")
        self.assertTrue(wait_until(lambda: screen.job.finished, self.app))
        text = (screen.saved_folder / "runs.csv").read_text(encoding="utf-8")
        self.assertNotIn("fixed_tuned", text)
        self.assertNotIn(",rl,", text)

    def test_no_scenario_and_bad_runs_are_refused(self):
        screen = self.open("experiment")
        self.click_button("None")
        self.click_button("Start experiment")
        self.assertIn("at least one scenario", screen.problem)
        self.click_button("[ ] rush_hour")
        self.app.handle_event(click(screen.runs._parts()[1].center))
        for _ in range(6):
            self.press(pygame.K_BACKSPACE)
        self.type_text("999")
        self.press(pygame.K_RETURN)
        self.assertIn("between 1 and", screen.runs.error)
        self.click_button("Start experiment")
        self.assertFalse(screen.running)

    def test_all_scenarios_button(self):
        screen = self.open("experiment")
        self.click_button("All")
        self.assertEqual(len(screen.scenarios.names), 7)
        self.click_button("None")
        self.assertEqual(screen.scenarios.names, [])

    def test_stop_keeps_only_runs_every_controller_finished(self):
        screen = self.open("experiment")
        screen.runs.set_value(40)  # 3 controllers x 40 runs; stop once the agent has started
        self.click_button("Start experiment")
        self.assertTrue(wait_until(lambda: screen.job.progress[0] >= 81, self.app))
        self.click_button("Stop")
        self.assertTrue(wait_until(lambda: screen.job.finished, self.app, 60))
        self.assertEqual(screen.job.state, "stopped", screen.job.error)
        self.assertIn("partial", self.app.toast[0])
        result = screen.job.result[1]
        counts = {len(v) for v in result.scenarios[0].records.values()}
        self.assertEqual(len(counts), 1)  # every controller has the same number of runs
        self.assertLess(counts.pop(), 40)
        self.assertIn("stopped early", (screen.saved_folder / "summary.md").read_text(encoding="utf-8"))

    def test_stop_before_every_controller_finished_a_run_saves_nothing(self):
        screen = self.open("experiment")
        screen.runs.set_value(40)
        self.click_button("Start experiment")
        self.assertTrue(wait_until(lambda: screen.job.progress[0] >= 1, self.app))
        self.click_button("Stop")
        self.assertTrue(wait_until(lambda: screen.job.finished, self.app, 60))
        self.assertIsNone(screen.job.result)
        self.assertIsNone(screen.saved_folder)
        self.assertFalse(self.paths.results_dir.exists() and any(self.paths.results_dir.iterdir()))

    def test_leaving_while_running_asks_first(self):
        screen = self.open("experiment")
        self.click_button("All")
        screen.runs.set_value(20)
        self.click_button("Start experiment")
        self.assertTrue(wait_until(lambda: screen.job.progress[0] >= 1, self.app))
        self.click_button("Back")
        self.assertIsNotNone(screen.dialog)
        self.press(pygame.K_ESCAPE)
        self.assertTrue(screen.running)
        self.click_button("Back")
        self.app.handle_event(click(screen.dialog.buttons[0].rect.center))
        self.assertTrue(wait_until(lambda: self.app.screen.name == "menu", self.app, 60))

    def test_model_outside_training_scenarios_gets_a_warning(self):
        screen = self.open("experiment")
        self.click_button("[x] rush_hour")
        self.click_button("[ ] low")
        self.assertIn("not on low", screen._scenario_note())
        self.draw()


class ResultsScreenTests(AppTestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        settings = settings_small()
        cls.result = run_experiment(settings, ["low", "high"], runs=2, agent=varied_agent(settings))
        cls.folder = save_experiment(cls.result, Path(cls.tmp.name), graphs=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        super().setUp()
        shutil.copytree(self.folder, self.paths.results_dir / self.folder.name)

    def test_empty_states_are_explained(self):
        shutil.rmtree(self.paths.results_dir)
        screen = self.open("results")
        self.assertEqual(screen.items, [])
        self.draw()
        self.click_button("Training graphs")
        self.assertEqual(screen.items, [])
        self.draw()

    def test_table_scenarios_and_graphs(self):
        screen = self.open("results")
        self.assertEqual(len(screen.items), 1)
        self.assertEqual(screen.sub_count, 2)
        first = self.draw()
        self.click_button("Scenario >")
        self.assertEqual(screen.sub, 1)
        self.click_button("Scenario >")
        self.assertEqual(screen.sub, 0)  # wraps
        self.assertNotEqual(pygame.image.tostring(first, "RGB"), pygame.image.tostring(self.draw(), "RGB")
                            if screen.sub else b"")
        self.click_button("Graphs")
        self.assertEqual(screen.view, "graphs")
        count = screen.sub_count
        self.assertGreater(count, 2)
        self.draw()
        self.press(pygame.K_RIGHT)
        self.assertEqual(screen.sub, 1)
        self.press(pygame.K_LEFT)
        self.press(pygame.K_LEFT)
        self.assertEqual(screen.sub, count - 1)
        self.draw()
        self.assertIsNotNone(screen._image_cache[1])
        self.click_button("Table")
        self.assertEqual(screen.view, "table")

    def test_selecting_between_several_experiments_and_a_damaged_one(self):
        shutil.copytree(self.folder, self.paths.results_dir / "experiment_20991231_000000_copy")
        bad = self.paths.results_dir / "experiment_20991230_000000_bad"
        bad.mkdir()
        (bad / "experiment.json").write_text("nope", encoding="utf-8")
        screen = self.open("results")
        self.assertEqual(len(screen.items), 3)
        self.assertFalse(screen.newer.enabled)
        self.click_button("Older")
        self.assertIn("damaged", screen.message)
        self.draw()
        self.assertEqual(screen.sub_count, 0)
        self.click_button("Older")
        self.assertEqual(screen.message, "")
        self.assertFalse(screen.older.enabled)
        self.click_button("Newer")
        self.click_button("Newer")
        self.assertEqual(screen.index, 0)
        # clicking a row selects it
        self.app.handle_event(click(screen._row_rects[2].center))
        self.assertEqual(screen.index, 2)

    def test_training_graphs_mode(self):
        self.paths.graph_dir.mkdir(parents=True)
        shutil.copy(next((self.folder / "graphs").glob("*.png")), self.paths.graph_dir / "training_x_reward.png")
        screen = self.open("results")
        self.click_button("Training graphs")
        self.assertEqual([i[0] for i in screen.items], ["training_x_reward"])
        self.assertFalse(screen.table_button.enabled)
        self.draw()
        self.assertIsNotNone(screen._image_cache[1])
        (self.paths.graph_dir / "training_x_reward.png").write_bytes(b"not a png")
        screen._image_cache = None
        self.draw()  # a damaged picture is reported, not a crash
        self.assertIsNone(screen._image_cache[1])

    def test_opens_with_the_requested_folder_selected(self):
        newer = self.paths.results_dir / "experiment_20991231_000000_copy"
        shutil.copytree(self.folder, newer)
        screen = self.open("results", folder=self.paths.results_dir / self.folder.name)
        self.assertEqual(screen.items[screen.index][1].name, self.folder.name)
        self.assertEqual(screen.index, 1)


class SettingsScreenTests(AppTestCase):
    def row(self, screen, name):
        return next(r for r in screen.rows if r[0].name == name)

    def test_change_and_save_applies_and_writes_the_file(self):
        screen = self.open("settings")
        self.assertFalse(screen.save_button.enabled)
        _, _, minus, value, plus = self.row(screen, "scenario")
        self.app.handle_event(click(plus.center))
        self.assertTrue(screen.form.dirty)
        self.assertTrue(screen.save_button.enabled)
        self.click_button("Display")
        _, _, _, theme_box, _ = self.row(screen, "theme")
        self.app.handle_event(click(theme_box.center))  # cycles dark -> light
        self.click_button("Save")
        self.assertEqual(self.app.settings.display.theme, "light")
        self.assertEqual(self.app.theme.name, "light")
        loaded = Settings.load(self.paths.settings_file)
        self.assertEqual(loaded.traffic.scenario, self.app.settings.traffic.scenario)
        self.assertNotEqual(loaded.traffic.scenario, "rush_hour")
        self.assertFalse(screen.form.dirty)
        self.draw()

    def test_typing_a_number(self):
        screen = self.open("settings")
        _, _, _, value, _ = self.row(screen, "seed")
        self.app.handle_event(click(value.center))
        self.assertIsNotNone(screen.editing)
        for _ in range(10):
            self.press(pygame.K_BACKSPACE)
        self.type_text("2024")
        self.press(pygame.K_RETURN)
        self.assertEqual(screen.form.value(screen.rows[1][0]), 2024)
        self.click_button("Save")
        self.assertEqual(self.app.settings.traffic.seed, 2024)

    def test_escape_cancels_typing_without_leaving(self):
        screen = self.open("settings")
        _, _, _, value, _ = self.row(screen, "seed")
        self.app.handle_event(click(value.center))
        self.type_text("9")
        self.press(pygame.K_ESCAPE)
        self.assertIsNone(screen.editing)
        self.assertEqual(self.app.screen.name, "settings")
        self.assertEqual(screen.form.value(screen.rows[1][0]), 3)

    def test_bad_input_is_explained_and_not_saved(self):
        screen = self.open("settings")
        _, _, _, value, _ = self.row(screen, "seed")
        self.app.handle_event(click(value.center))
        for _ in range(10):
            self.press(pygame.K_BACKSPACE)
        self.type_text("1.5")
        self.press(pygame.K_RETURN)
        self.assertTrue(screen.form.problems())
        self.draw()
        self.click_button("Save")
        self.assertIn("Not saved", screen.status)
        self.assertFalse(self.paths.settings_file.exists())
        self.assertEqual(self.app.settings.traffic.seed, 3)
        self.draw()

    def test_a_rule_between_two_settings_blocks_saving(self):
        screen = self.open("settings")
        self.click_button("Lights")
        _, _, _, value, _ = self.row(screen, "max_green")
        self.app.handle_event(click(value.center))
        for _ in range(10):
            self.press(pygame.K_BACKSPACE)
        self.type_text("8")
        self.press(pygame.K_RETURN)
        self.click_button("Save")
        self.assertIn("Not saved", screen.status)
        self.assertFalse(self.paths.settings_file.exists())

    def test_leaving_with_unsaved_changes_asks_and_revert_defaults_work(self):
        screen = self.open("settings")
        _, _, _, _, plus = self.row(screen, "seed")
        self.app.handle_event(click(plus.center))
        self.click_button("Back")
        self.assertIsNotNone(screen.dialog)
        self.press(pygame.K_ESCAPE)  # Stay here
        self.assertEqual(self.app.screen.name, "settings")
        self.click_button("Revert")
        self.assertFalse(screen.form.dirty)
        self.click_button("Defaults")
        self.assertIsNotNone(screen.dialog)
        self.press(pygame.K_ESCAPE)
        self.assertFalse(screen.form.dirty)
        self.click_button("Defaults")
        self.app.handle_event(click(screen.dialog.buttons[0].rect.center))
        self.assertTrue(screen.form.dirty)
        self.assertEqual(self.app.settings.traffic.seed, 3)  # nothing applied until Save
        self.click_button("Back")
        self.app.handle_event(click(screen.dialog.buttons[0].rect.center))  # Discard
        self.assertEqual(self.app.screen.name, "menu")
        self.assertFalse(self.paths.settings_file.exists())

    def test_every_page_draws_and_every_field_is_reachable(self):
        screen = self.open("settings")
        window = pygame.Rect(0, 0, *self.size)
        from ui.settings_form import PAGES
        for page in PAGES:
            self.click_button(page)
            self.assertEqual(len(screen.rows), len(PAGES[page]))
            for field, label, minus, value, plus in screen.rows:
                for rect in (minus, value, plus):
                    self.assertTrue(window.contains(rect), field.label)
            self.draw()

    def test_a_changed_theme_applies_to_the_menu(self):
        screen = self.open("settings")
        self.click_button("Display")
        _, _, _, theme_box, _ = self.row(screen, "theme")
        self.app.handle_event(click(theme_box.center))
        self.click_button("Save")
        menu = self.open("menu")
        self.assertEqual(menu.theme.name, "light")


class AboutTests(AppTestCase):
    def test_about_back(self):
        self.open("about")
        self.draw()
        self.click_button("Back")
        self.assertEqual(self.app.screen.name, "menu")


class RenderTests(AppTestCase):
    def test_every_screen_draws_at_several_sizes_and_both_themes(self):
        for theme in ("dark", "light"):
            settings = settings_small(display={"theme": theme})
            for size in ((800, 600), (1280, 720), (1920, 1080)):
                for name in SCREENS:
                    surface = render_screen(name, settings, self.paths, size=size)
                    self.assertEqual(surface.get_size(), size)
                    colours = {tuple(surface.get_at((x, y))) for x in range(0, size[0], 23)
                               for y in range(0, size[1], 19)}
                    self.assertGreater(len(colours), 2, (name, size, theme))

    def test_buttons_never_overlap_each_other_or_leave_the_window(self):
        for size in ((800, 600), (1280, 720), (1920, 1080)):
            for name in ("menu", "compare", "training", "experiment", "results", "settings", "about"):
                app = App(self.settings, self.paths, size=size)
                screen = app.go(name)
                surface = pygame.Surface(size)
                app.draw(surface)
                window = pygame.Rect(0, 0, *size)
                rects = [(b.label, b.rect) for b in screen.buttons]
                for label, rect in rects:
                    self.assertTrue(window.contains(rect), (name, size, label, rect))
                for i, (la, ra) in enumerate(rects):
                    for lb, rb in rects[i + 1:]:
                        self.assertFalse(ra.colliderect(rb), (name, size, la, lb))

    def test_unknown_screen_is_a_clear_error(self):
        with self.assertRaises(ValueError):
            self.app.go("nope")

    def test_resize_event_updates_the_layout(self):
        self.open("menu")
        self.app.handle_event(pygame.event.Event(pygame.VIDEORESIZE, w=1000, h=640, size=(1000, 640)))
        self.assertEqual(self.app.size, (1000, 640))
        surface = pygame.Surface((1000, 640))
        self.app.draw(surface)
        self.assertTrue(pygame.Rect(0, 0, 1000, 640).contains(self.app.screen.buttons[-1].rect))


if __name__ == "__main__":
    unittest.main()
