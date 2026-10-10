import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import main
from utils.logging_setup import teardown_logging

requires_pygame = unittest.skipIf(importlib.util.find_spec("pygame") is None, "pygame is not installed")


class CommandLineTests(unittest.TestCase):
    """Run the real entry point, but keep logs and settings out of the project folder."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.addCleanup(teardown_logging)
        self.dir = Path(tmp.name)
        for name, value in (("LOG_DIR", self.dir / "logs"),
                            ("MODEL_DIR", self.dir / "models"),
                            ("CSV_DIR", self.dir / "csv"),
                            ("GRAPH_DIR", self.dir / "graphs"),
                            ("RESULTS_DIR", self.dir / "results"),
                            ("SETTINGS_FILE", self.dir / "user_settings.json")):
            patcher = mock.patch.object(main, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(main, "ensure_directories", lambda: [])
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_overview(self):
        code, out, _ = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("Phase 8", out)
        self.assertIn("--menu", out)
        self.assertIn("--experiment", out)
        self.assertIn("--train", out)
        self.assertIn("--window", out)
        self.assertIn("--demo", out)

    def test_demo_runs_the_fixed_controller_and_reports_metrics(self):
        code, out, err = self.run_main("--demo", "--duration", "120", "--seed", "5", "--scenario", "high")
        self.assertEqual(code, 0, err)
        for fragment in ("Fixed-time: NS green 30 s", "Vehicles served", "Average waiting time",
                         "Average queue length", "Safety check (no crossing conflicts): PASSED"):
            self.assertIn(fragment, out)

    def test_demo_green_time_options_are_used(self):
        _, out, _ = self.run_main("--demo", "--duration", "60", "--ns-green", "20", "--ew-green", "40")
        self.assertIn("NS green 20 s, EW green 40 s", out)

    def test_same_seed_gives_the_same_report(self):
        args = ("--demo", "--duration", "180", "--seed", "9", "--scenario", "random")
        self.assertEqual(self.run_main(*args)[1], self.run_main(*args)[1])

    def test_bad_values_give_friendly_messages_and_exit_code_2(self):
        for argv, fragment in (
            (("--demo", "--duration", "-5"), "simulation.duration"),
            (("--demo", "--seed", "-1"), "traffic.seed"),
            (("--demo", "--ns-green", "5"), "fixed.ns_green"),
            (("--demo", "--ew-green", "999"), "fixed.ew_green"),
            (("--demo", "--report-every", "0"), "--report-every"),
            (("--config", str(Path("no_such_file.json"))), "not found"),
        ):
            code, out, err = self.run_main(*argv)
            self.assertEqual(code, 2, argv)
            self.assertIn(fragment, err, argv)
            self.assertNotIn("Traceback", err + out)

    def test_a_settings_file_is_used_and_cli_options_override_it(self):
        path = self.dir / "mine.json"
        path.write_text(json.dumps({"traffic": {"scenario": "uneven", "seed": 3},
                                    "simulation": {"duration": 90}}), encoding="utf-8")
        _, out, _ = self.run_main("--demo", "--config", str(path))
        self.assertIn("uneven", out)
        self.assertIn("Seed       : 3", out)
        _, out, _ = self.run_main("--demo", "--config", str(path), "--seed", "8")
        self.assertIn("Seed       : 8", out)

    def test_write_settings_creates_a_file_and_refuses_to_overwrite_it(self):
        target = self.dir / "settings.json"
        self.assertEqual(self.run_main("--write-settings", "--config", str(target))[0], 0)
        self.assertIn("fixed", json.loads(target.read_text(encoding="utf-8")))
        code, out, _ = self.run_main("--write-settings", "--config", str(target))
        self.assertEqual(code, 1)
        self.assertIn("--force", out)
        self.assertEqual(self.run_main("--write-settings", "--config", str(target), "--force")[0], 0)

    def test_list_scenarios(self):
        code, out, _ = self.run_main("--list-scenarios")
        self.assertEqual(code, 0)
        for name in ("low", "rush_hour", "uneven", "random"):
            self.assertIn(name, out)

    @requires_pygame
    def test_screenshot_option_writes_a_png(self):
        target = self.dir / "shots" / "frame.png"
        code, out, err = self.run_main("--screenshot", str(target), "--screenshot-at", "30",
                                       "--scenario", "high")
        self.assertEqual(code, 0, err)
        self.assertTrue(target.is_file())
        self.assertIn("Screenshot saved", out)

    def test_env_demo_plays_the_environment(self):
        code, out, err = self.run_main("--env-demo", "--duration", "90", "--env-episodes", "2")
        self.assertEqual(code, 0, err)
        for fragment in ("random agent", "Episode 2", "18 states", "PASSED"):
            self.assertIn(fragment, out)
        code, _, err = self.run_main("--env-demo", "--env-episodes", "0")
        self.assertEqual(code, 2)
        self.assertIn("--env-episodes", err)

    TRAIN = ("--train", "--episodes", "6", "--duration", "60", "--scenario", "rush_hour")

    def test_train_saves_a_model_and_a_log_that_can_be_used(self):
        code, out, err = self.run_main(*self.TRAIN)
        self.assertEqual(code, 0, err)
        model = self.dir / "models" / "q_learning_model.json"
        self.assertTrue(model.is_file())
        self.assertIn("Model saved", out)
        self.assertIn("PASSED", out)
        logs = list((self.dir / "csv").glob("training_*.csv"))
        self.assertEqual(len(logs), 1)
        self.assertEqual(len(logs[0].read_text(encoding="utf-8").splitlines()), 7)  # header + 6
        code, out, err = self.run_main("--model-info")
        self.assertEqual(code, 0, err)
        for fragment in ("Trained    : 6 episodes", "rush_hour", "NS traffic high", "learning_rate"):
            self.assertIn(fragment, out)
        code, out, err = self.run_main("--demo", "--controller", "rl", "--duration", "120",
                                       "--scenario", "rush_hour")
        self.assertEqual(code, 0, err)
        self.assertIn("Q-Learning agent (learned policy, epsilon 0; trained 6 episodes", out)
        self.assertIn("PASSED", out)

    def test_train_options_are_used(self):
        model = self.dir / "mine.json"
        code, out, err = self.run_main(*self.TRAIN, "--model", str(model), "--no-log",
                                       "--learning-rate", "0.3", "--discount", "0.8",
                                       "--epsilon", "0.5", "--epsilon-decay", "0.9",
                                       "--epsilon-min", "0.1", "--train-scenarios", "low,high")
        self.assertEqual(code, 0, err)
        self.assertFalse((self.dir / "csv").exists() and any((self.dir / "csv").iterdir()))
        data = json.loads(model.read_text(encoding="utf-8"))
        self.assertEqual(data["parameters"]["learning_rate"], 0.3)
        self.assertEqual(data["parameters"]["discount_factor"], 0.8)
        self.assertEqual(data["parameters"]["epsilon_start"], 0.5)
        self.assertEqual(data["training"]["scenarios"], ["low", "high"])
        self.assertIsNotNone(data["training"]["best_episode"])
        self.assertAlmostEqual(data["training"]["final_epsilon"], max(0.1, 0.5 * 0.9 ** 6))

    def test_train_never_overwrites_a_model_by_accident(self):
        self.run_main(*self.TRAIN)
        model = self.dir / "models" / "q_learning_model.json"
        before = model.read_text(encoding="utf-8")
        code, out, _ = self.run_main(*self.TRAIN)
        self.assertEqual(code, 1)
        self.assertIn("--continue-training", out)
        self.assertEqual(model.read_text(encoding="utf-8"), before)
        self.assertEqual(self.run_main(*self.TRAIN, "--force")[0], 0)

    def test_continue_training_adds_episodes(self):
        self.run_main(*self.TRAIN)
        code, _, err = self.run_main(*self.TRAIN, "--continue-training")
        self.assertEqual(code, 0, err)
        model = self.dir / "models" / "q_learning_model.json"
        self.assertEqual(json.loads(model.read_text(encoding="utf-8"))["training"]["episodes"], 12)

    def test_train_all_scenarios_shortcut(self):
        code, _, err = self.run_main("--train", "--episodes", "8", "--duration", "30",
                                     "--train-scenarios", "all", "--no-log")
        self.assertEqual(code, 0, err)
        data = json.loads((self.dir / "models" / "q_learning_model.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["training"]["scenarios"]), 7)

    def test_ctrl_c_during_training_saves_the_model(self):
        with mock.patch.object(main.Trainer, "train", side_effect=KeyboardInterrupt):
            code, out, _ = self.run_main(*self.TRAIN)
        self.assertEqual(code, 130)
        self.assertIn("Model saved", out)
        self.assertTrue((self.dir / "models" / "q_learning_model.json").is_file())

    def test_bad_training_and_model_input_gives_friendly_messages(self):
        for argv, fragment in (
            (("--train", "--episodes", "0"), "rl.episodes"),
            (("--train", "--learning-rate", "5"), "rl.learning_rate"),
            (("--train", "--epsilon", "2"), "rl.epsilon"),
            (("--train", "--epsilon-min", "0.9", "--epsilon", "0.5"), "epsilon_min"),
            (("--train", "--train-scenarios", "low,nope"), "nope"),
            (("--demo", "--controller", "rl"), "not found"),
            (("--model-info",), "not found"),
        ):
            code, out, err = self.run_main(*argv)
            self.assertEqual(code, 2, argv)
            self.assertIn(fragment, err, argv)
            self.assertNotIn("Traceback", err + out)
        bad = self.dir / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        code, _, err = self.run_main("--model-info", "--model", str(bad))
        self.assertEqual(code, 2)
        self.assertIn("damaged", err)

    def test_a_model_trained_with_other_state_settings_is_refused(self):
        self.run_main(*self.TRAIN)
        path = self.dir / "other.json"
        path.write_text(json.dumps({"rl": {"medium_traffic": 7}}), encoding="utf-8")
        code, _, err = self.run_main("--demo", "--controller", "rl", "--config", str(path))
        self.assertEqual(code, 2)
        self.assertIn("state design", err)

    @requires_pygame
    def test_screenshot_can_show_the_trained_agent(self):
        self.run_main(*self.TRAIN)
        target = self.dir / "rl.png"
        code, _, err = self.run_main("--screenshot", str(target), "--controller", "rl",
                                     "--screenshot-at", "30")
        self.assertEqual(code, 0, err)
        self.assertTrue(target.is_file())

    def test_window_option_validation(self):
        code, _, err = self.run_main("--screenshot", str(self.dir / "frame.txt"))
        self.assertEqual(code, 2)
        self.assertIn(".png", err)
        code, _, err = self.run_main("--screenshot", str(self.dir / "f.png"), "--screenshot-at", "-1")
        self.assertEqual(code, 2)
        self.assertIn("--screenshot-at", err)
        with self.assertRaises(SystemExit):  # argparse rejects a speed that is not offered
            self.run_main("--window", "--speed", "3")

    def test_window_opens_with_chosen_options(self):
        fake = mock.Mock()
        with mock.patch.object(main, "_load_ui", return_value=fake):
            code, _, err = self.run_main("--window", "--speed", "5", "--paused", "--scenario", "low")
        self.assertEqual(code, 0, err)
        args, kwargs = fake.run_window.call_args
        self.assertEqual(args[0].traffic.scenario, "low")
        self.assertEqual((kwargs["speed"], kwargs["paused"]), (5.0, True))

    def test_missing_pygame_gives_a_friendly_message(self):
        with mock.patch.object(main, "_load_ui", return_value=None):
            code, out, err = self.run_main("--window")
        self.assertEqual(code, 1)
        self.assertIn("pip install -r requirements.txt", err)
        self.assertNotIn("Traceback", err + out)

    def test_technical_details_go_to_the_log_file_not_the_console(self):
        code, _, err = self.run_main("--demo", "--duration", "30")
        teardown_logging()
        self.assertEqual((code, err), (0, ""))
        log_text = (self.dir / "logs" / "application.log").read_text(encoding="utf-8")
        self.assertIn("Demo started", log_text)
        self.assertIn("Demo finished", log_text)

    EXPERIMENT = ("--experiment", "--runs", "2", "--duration", "120", "--experiment-scenarios", "low,high",
                  "--seed", "3")

    def test_experiment_without_rl_writes_files(self):
        code, out, err = self.run_main(*self.EXPERIMENT, "--no-rl", "--no-graphs")
        self.assertEqual(code, 0, err)
        folders = list((self.dir / "results").iterdir())
        self.assertEqual(len(folders), 1)
        for name in ("summary.md", "runs.csv", "summary.csv", "comparison.csv", "experiment.json"):
            self.assertTrue((folders[0] / name).is_file(), name)
        self.assertFalse((folders[0] / "graphs").exists())
        self.assertNotIn(",rl,", (folders[0] / "runs.csv").read_text(encoding="utf-8"))

    def test_experiment_with_a_trained_model_and_graphs(self):
        self.assertEqual(self.run_main(*self.TRAIN)[0], 0)
        out_dir = self.dir / "out"
        code, out, err = self.run_main(*self.EXPERIMENT, "--results-dir", str(out_dir))
        self.assertEqual(code, 0, err)
        folder = next(out_dir.iterdir())
        self.assertIn(",rl,", (folder / "runs.csv").read_text(encoding="utf-8"))
        if importlib.util.find_spec("matplotlib") is None:
            return
        self.assertTrue(list((folder / "graphs").glob("*.png")))
        self.assertTrue(list((self.dir / "graphs").glob("training_*_reward.png")))

    def test_experiment_without_a_model_says_how_to_train(self):
        code, out, err = self.run_main(*self.EXPERIMENT)
        self.assertEqual(code, 1)
        self.assertIn("--train", out + err)
        self.assertFalse((self.dir / "results").exists() and any((self.dir / "results").iterdir()))

    def test_experiment_bad_input_gives_exit_code_2(self):
        for extra in (("--runs", "0"), ("--runs", "9999"), ("--experiment-scenarios", "low,nope")):
            code, _, err = self.run_main("--experiment", "--no-rl", *extra)
            self.assertEqual(code, 2, extra)
            self.assertTrue(err.strip(), extra)

    @requires_pygame
    def test_menu_screenshots_every_screen(self):
        for name in main.SCREEN_NAMES:
            target = self.dir / f"{name}.png"
            code, out, err = self.run_main("--menu", "--screen", name, "--screenshot", str(target))
            self.assertEqual(code, 0, err)
            self.assertTrue(target.read_bytes().startswith(b"\x89PNG"), name)

    def test_menu_screenshot_name_must_be_png(self):
        code, _, err = self.run_main("--menu", "--screenshot", str(self.dir / "x.jpg"))
        self.assertEqual(code, 2)
        self.assertIn(".png", err)

    @requires_pygame
    def test_menu_opens_the_window_with_chosen_start_screen(self):
        from ui import app as ui_app
        with mock.patch.object(ui_app, "run_app") as run:
            code, _, err = self.run_main("--menu", "--screen", "settings")
        self.assertEqual(code, 0, err)
        self.assertEqual(run.call_args.kwargs["start"], "settings")
        self.assertEqual(run.call_args.args[1].model_path.name, "q_learning_model.json")

    def test_missing_pygame_gives_a_friendly_message_for_the_menu(self):
        import builtins
        real = builtins.__import__

        def fake(name, *a, **k):
            if name == "ui" or name.startswith("ui.app"):
                raise ImportError("no pygame")
            return real(name, *a, **k)
        with mock.patch.object(builtins, "__import__", fake):
            code, _, err = self.run_main("--menu")
        self.assertEqual(code, 1)
        self.assertIn("pygame", err)


if __name__ == "__main__":
    unittest.main()
