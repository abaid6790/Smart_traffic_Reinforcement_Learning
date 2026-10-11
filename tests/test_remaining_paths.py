"""Phase 10: the last code paths that earlier tests did not reach.

Found with a coverage run: the real window loops, the entry point's safety nets, optional-library fallbacks and a few
guard clauses.  Each test checks behaviour the user can see, not just that a line ran.
"""

import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("MPLBACKEND", "Agg")

import main
from config.settings import ConfigError, Settings
from utils.logging_setup import teardown_logging

requires_pygame = unittest.skipIf(importlib.util.find_spec("pygame") is None, "pygame is not installed")


class FakeStdout(io.StringIO):
    """A stdout that has a file descriptor, like the real one (the entry point re-points it on a broken pipe)."""

    def fileno(self):
        return 1


class IsolatedMain(unittest.TestCase):
    """Run the real entry point with logs, models and results in a temporary folder."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.addCleanup(teardown_logging)
        self.dir = Path(tmp.name)
        for name, value in (("LOG_DIR", self.dir / "logs"), ("MODEL_DIR", self.dir / "models"),
                            ("CSV_DIR", self.dir / "csv"), ("GRAPH_DIR", self.dir / "graphs"),
                            ("RESULTS_DIR", self.dir / "results"), ("SETTINGS_FILE", self.dir / "user_settings.json")):
            patcher = mock.patch.object(main, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(main, "ensure_directories", lambda: [])
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_main(self, *argv, out=None):
        out, err = out or io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main.main(list(argv))
        return code, out.getvalue(), err.getvalue()


class EntryPointSafetyNetTests(IsolatedMain):
    def fails_with(self, error):
        return mock.patch.object(main, "_dispatch", side_effect=error)

    def test_ctrl_c_stops_politely(self):
        with self.fails_with(KeyboardInterrupt()):
            code, out, _ = self.run_main()
        self.assertEqual(code, 130)
        self.assertIn("Stopped by user", out)

    def test_a_closed_pipe_is_not_an_error(self):
        with self.fails_with(BrokenPipeError()), mock.patch.object(main.os, "dup2"), \
                mock.patch.object(main.os, "open", return_value=3):
            code, _, err = self.run_main(out=FakeStdout())
        self.assertEqual(code, 0)
        self.assertEqual(err, "")

    def test_a_file_problem_gets_a_plain_message_and_a_log_pointer(self):
        with self.fails_with(PermissionError(13, "Permission denied", "x.json")):
            code, _, err = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("A file or folder could not be used: Permission denied", err)
        self.assertIn("application.log", err)

    def test_an_unexpected_bug_never_shows_a_traceback(self):
        with self.fails_with(RuntimeError("boom")):
            code, _, err = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("Something unexpected went wrong", err)
        self.assertNotIn("Traceback", err)
        self.assertNotIn("boom", err)
        self.assertIn("boom", (self.dir / "logs" / "application.log").read_text(encoding="utf-8"))

    def test_a_model_problem_is_explained(self):
        from agents.q_learning import ModelError
        with self.fails_with(ModelError("the file is damaged")):
            code, _, err = self.run_main()
        self.assertEqual(code, 2)
        self.assertIn("There is a problem with the model: the file is damaged", err)


class OptionalLibraryFallbackTests(IsolatedMain):
    def test_experiment_without_matplotlib_still_saves_the_numbers(self):
        real = main.save_experiment
        calls = []

        def fake(result, root, graphs=True):
            calls.append(graphs)
            if graphs:
                raise ImportError("no matplotlib")
            return real(result, root, graphs=False)

        with mock.patch.object(main, "save_experiment", fake):
            code, out, _ = self.run_main("--experiment", "--no-rl", "--no-tune", "--runs", "1", "--duration", "60",
                                         "--scenario", "low")
        self.assertEqual(code, 0)
        self.assertEqual(calls, [True, False])
        self.assertIn("matplotlib is not installed", out)
        folders = list((self.dir / "results").glob("experiment_*"))
        self.assertEqual(len(folders), 1)
        self.assertTrue((folders[0] / "summary.md").exists())
        self.assertFalse((folders[0] / "graphs").exists())

    def test_training_without_matplotlib_still_saves_the_model(self):
        with mock.patch.dict(sys.modules, {"evaluation.graphs": None}):  # makes "import" raise ImportError
            code, out, _ = self.run_main("--train", "--episodes", "3", "--duration", "60", "--scenario", "low")
        self.assertEqual(code, 0)
        self.assertIn("matplotlib is not installed", out)
        self.assertTrue((self.dir / "models" / "q_learning_model.json").exists())

    def test_saving_an_experiment_reports_missing_matplotlib_to_the_caller(self):
        from evaluation.experiment import run_experiment
        from evaluation.export import save_experiment
        from tests.test_experiment import settings_for
        result = run_experiment(settings_for(duration=60.0), ["low"], runs=1, agent=None, tune_runs=1, tune=False)
        with mock.patch.dict(sys.modules, {"evaluation.graphs": None}), self.assertRaises(ImportError):
            save_experiment(result, self.dir / "results", graphs=True)


class ReportTextTests(unittest.TestCase):
    def test_a_comparison_without_runs_reads_not_available(self):
        from evaluation.export import _verdict_text
        empty = types.SimpleNamespace(paired=types.SimpleNamespace(n=0, candidate_better=0, verdict="x",
                                                                   differences=types.SimpleNamespace(ci_low=None)))
        self.assertEqual(_verdict_text(empty, None), "n/a")

    def test_unknown_scenario_and_empty_series(self):
        from evaluation.experiment import _average_series, run_experiment
        from tests.test_experiment import settings_for
        result = run_experiment(settings_for(duration=60.0), ["low"], runs=1, agent=None, tune=False)
        self.assertEqual(result.scenario("low").scenario, "low")
        with self.assertRaises(KeyError):
            result.scenario("no_such_scenario")
        empty = _average_series([])
        self.assertEqual(len(empty.times), 0)


class GuardClauseTests(unittest.TestCase):
    def test_a_road_too_short_for_a_few_vehicles_is_refused(self):
        with self.assertRaises(ConfigError) as caught:
            Settings().with_changes("simulation", road_length=20.0, vehicle_length=10.0, min_gap=5.0)
        self.assertIn("road_length is too short", " ".join(caught.exception.problems))

    def test_tuning_can_be_asked_for_a_specific_scenario(self):
        from controllers.tuning import tune_fixed_time
        from tests.test_experiment import settings_for
        result = tune_fixed_time(settings_for(duration=60.0, scenario="rush_hour"), scenario="low", runs=1,
                                 candidates=(10, 20))
        self.assertEqual(result.scenario, "low")
        with self.assertRaises(ValueError):
            tune_fixed_time(settings_for(duration=60.0), runs=0)

    def test_training_refuses_a_bad_or_unconfirmed_plan(self):
        from training.workflow import TrainingPlan, run_training
        from tests.test_experiment import settings_for
        with tempfile.TemporaryDirectory() as tmp:
            model = Path(tmp) / "m.json"
            bad = TrainingPlan(settings_for(duration=60.0), [], 3, model)
            with self.assertRaises(ValueError):
                run_training(bad, Path(tmp), Path(tmp))
            ok = TrainingPlan(settings_for(duration=60.0), ["low"], 2, model)
            run_training(ok, Path(tmp), Path(tmp))
            self.assertTrue(model.exists())
            again = TrainingPlan(settings_for(duration=60.0), ["low"], 2, model)  # a model exists now
            self.assertTrue(again.would_replace_model)
            with self.assertRaises(ValueError) as caught:
                run_training(again, Path(tmp), Path(tmp))
            self.assertIn("already exists", str(caught.exception))
            self.assertEqual(model.stat().st_size > 0, True)

    def test_training_on_empty_roads_does_not_crash_the_validation_step(self):
        from tests.test_experiment import settings_for
        from training.trainer import Trainer
        settings = settings_for(duration=60.0, scenario="low", validation_every=1, validation_runs=1)
        settings = settings.with_changes("traffic", rate_scale=0.0001)  # (nearly) no vehicles arrive
        result = Trainer(settings).train(episodes=2)
        self.assertEqual(result.episodes_done, 2)


class JobEdgeTests(unittest.TestCase):
    def test_a_job_that_never_started_is_harmless(self):
        from ui.jobs import BackgroundJob
        job = BackgroundJob("idle", lambda j: None)
        self.assertEqual(job.elapsed, 0.0)
        job.resume()  # not paused: nothing happens
        job.request_stop()  # not running: nothing happens
        self.assertEqual(job.state, "idle")
        self.assertTrue(job.wait(0.1))


@requires_pygame
class WindowLoopTests(unittest.TestCase):
    """The real event loops, driven with scripted events instead of a person."""

    def tearDown(self):
        import pygame
        pygame.quit()

    def test_the_application_loop_runs_resizes_and_quits(self):
        import pygame
        from ui import app as ui_app
        settings = Settings().with_changes("display", fps=240)
        tiny = pygame.event.Event(pygame.VIDEORESIZE, size=(100, 100), w=100, h=100)
        script = iter([[], [tiny], [], [pygame.event.Event(pygame.QUIT)]])
        sizes = []
        real_set_mode = pygame.display.set_mode

        def spy(size, *args, **kwargs):
            sizes.append(tuple(size))
            return real_set_mode(size, *args, **kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            paths = ui_app.AppPaths(Path(tmp) / "m.json", Path(tmp), Path(tmp), Path(tmp), Path(tmp) / "s.json")
            with mock.patch.object(pygame.event, "get", side_effect=lambda: next(script)), \
                    mock.patch.object(pygame.display, "set_mode", spy):
                ui_app.run_app(settings, paths)
        # first the configured size, then the window is made bigger again because 100x100 is below the minimum
        self.assertEqual(sizes[0], (settings.display.window_width, settings.display.window_height))
        self.assertEqual(sizes[-1], ui_app.MIN_WINDOW)

    def test_repeated_screen_errors_close_the_application_with_a_message(self):
        import pygame
        from ui import app as ui_app
        from ui.screens.menu import MenuScreen
        settings = Settings().with_changes("display", fps=240)
        err = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            paths = ui_app.AppPaths(Path(tmp) / "m.json", Path(tmp), Path(tmp), Path(tmp), Path(tmp) / "s.json")
            with mock.patch.object(pygame.event, "get", return_value=[]), \
                    mock.patch.object(MenuScreen, "draw_content", side_effect=RuntimeError("bug")), \
                    self.assertLogs("ui.app", level="ERROR"), contextlib.redirect_stderr(err):
                ui_app.run_app(settings, paths)
        self.assertTrue(err.getvalue().strip())
        self.assertNotIn("Traceback", err.getvalue())

    def test_the_simulation_window_loop_runs_and_quits(self):
        import pygame
        from controllers.fixed_controller import FixedTimeController
        from ui import simulation_screen
        settings = Settings().with_changes("display", fps=240)
        script = iter([[], [], [pygame.event.Event(pygame.QUIT)]])
        with mock.patch.object(pygame.event, "get", side_effect=lambda: next(script)):
            simulation_screen.run_window(settings, FixedTimeController(settings), speed=1, paused=False)

    def test_application_default_paths_are_the_project_folders(self):
        from ui.app import AppPaths
        from utils import paths
        default = AppPaths.default()
        self.assertEqual(default.settings_file, paths.SETTINGS_FILE)
        self.assertEqual(default.results_dir, paths.RESULTS_DIR)
        self.assertEqual(default.model_path.parent, paths.MODEL_DIR)

    def test_a_model_file_that_cannot_be_read_is_damaged_not_missing(self):
        """A file we cannot open must not look like "no model yet" (which invites training over it)."""
        from ui.app import App, AppPaths
        with tempfile.TemporaryDirectory() as tmp:
            model = Path(tmp) / "model.json"
            app = App(Settings(), AppPaths(model, Path(tmp), Path(tmp), Path(tmp), Path(tmp) / "s.json"), size=(900, 600))
            self.assertEqual(app.model_status()[0], "none")  # really missing
            model.mkdir()  # a folder where the file should be
            self.assertEqual(app.model_status()[0], "bad")
            model.rmdir()
            model.write_text("{}", encoding="utf-8")
            with mock.patch.object(Path, "stat", side_effect=PermissionError(13, "Permission denied")):
                status, message = app.model_status()
        self.assertEqual(status, "bad")
        self.assertIn("cannot be read (Permission denied)", message)

    def test_hovering_a_button_shows_its_explanation_at_the_bottom(self):
        import pygame
        from ui.app import App, AppPaths
        with tempfile.TemporaryDirectory() as tmp:
            app = App(Settings(), AppPaths(Path(tmp) / "m.json", Path(tmp), Path(tmp), Path(tmp), Path(tmp) / "s.json"),
                      size=(1000, 700))
            app.go("menu")
            surface = pygame.Surface(app.size)
            app.draw(surface)
            button = app.screen.buttons[0]
            footer = pygame.Rect(0, app.size[1] - 40, app.size[0], 40)
            before = pygame.image.tostring(surface.subsurface(footer), "RGB")
            app.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=button.rect.center, rel=(0, 0), buttons=(0, 0, 0)))
            app.draw(surface)
            after = pygame.image.tostring(surface.subsurface(footer), "RGB")
        self.assertTrue(button.tooltip)
        self.assertNotEqual(before, after, "the explanation of the hovered button was not drawn")


if __name__ == "__main__":
    unittest.main()
