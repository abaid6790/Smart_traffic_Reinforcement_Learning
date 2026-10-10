"""Phase 8 logic that needs no pygame: jobs, settings form, results data, training workflow."""

import importlib.util
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from config.settings import ConfigError, Settings
from evaluation.experiment import run_experiment
from evaluation.export import save_experiment
from tests.test_experiment import settings_for, varied_agent
from training.workflow import TrainingPlan, run_training
from ui import jobs
from ui.jobs import BackgroundJob
from ui.results_data import list_experiments, list_graphs, read_experiment, scenario_names, scenario_view
from ui.settings_form import ALL_FIELDS, FIELD_BY_KEY, PAGES, SettingsForm


def wait_for(predicate, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return True
        time.sleep(0.01)
    return False


class JobTests(unittest.TestCase):
    def test_runs_reports_and_keeps_the_result(self):
        def work(job):
            for i in range(3):
                job.report(i + 1, 3, f"step {i + 1}")
            return "answer"
        job = BackgroundJob("t", work)
        self.assertEqual(job.state, jobs.IDLE)
        job.start()
        self.assertTrue(job.wait(5))
        self.assertEqual(job.state, jobs.DONE)
        self.assertEqual(job.result, "answer")
        self.assertEqual(job.progress, (3, 3, "step 3"))
        self.assertEqual(job.fraction, 1.0)

    def test_errors_become_friendly_failed_state(self):
        for exc, text in ((ConfigError(["bad value"]), "bad value"), (ValueError("nope"), "nope"),
                          (KeyError("x"), "Unexpected error")):
            def work(job, exc=exc):
                raise exc
            job = BackgroundJob("t", work)
            with self.assertLogs("ui.jobs", level="ERROR"):
                job.start()
                job.wait(5)
            self.assertEqual(job.state, jobs.FAILED)
            self.assertIn(text, job.error)

    def test_stop_marks_the_job_stopped(self):
        def work(job):
            while not job.should_stop():
                time.sleep(0.005)
            return 1
        job = BackgroundJob("t", work)
        job.start()
        self.assertTrue(job.active)
        job.request_stop()
        self.assertEqual(job.state, jobs.STOPPING)
        job.wait(5)
        self.assertEqual(job.state, jobs.STOPPED)

    def test_pause_blocks_the_work_and_resume_continues(self):
        counter = []

        def work(job):
            for _ in range(200):
                job.wait_if_paused()
                if job.should_stop():
                    return
                counter.append(1)
                time.sleep(0.002)
        job = BackgroundJob("t", work)
        job.start()
        wait_for(lambda: len(counter) > 3)
        job.pause()
        self.assertEqual(job.state, jobs.PAUSED)
        time.sleep(0.05)
        frozen = len(counter)
        time.sleep(0.1)
        self.assertLessEqual(len(counter) - frozen, 1)
        job.resume()
        self.assertTrue(wait_for(lambda: len(counter) > frozen + 5))
        job.request_stop()
        job.wait(5)

    def test_stop_wakes_a_paused_job(self):
        gate = threading.Event()

        def work(job):
            gate.wait(5)
            job.wait_if_paused()  # blocks while paused
            return "x"
        job = BackgroundJob("t", work)
        job.pause()  # no effect yet: not running
        job.start()
        job.pause()
        job.request_stop()
        gate.set()
        self.assertTrue(job.wait(5))
        self.assertTrue(job.finished)

    def test_cannot_start_twice_while_active_but_can_restart_after(self):
        gate = threading.Event()
        job = BackgroundJob("t", lambda j: gate.wait(5))
        job.start()
        with self.assertRaises(RuntimeError):
            job.start()
        gate.set()
        job.wait(5)
        job.start()
        job.wait(5)
        self.assertEqual(job.state, jobs.DONE)

    def test_eta_needs_progress(self):
        gate = threading.Event()

        def work(job):
            job.report(1, 4, "a")
            gate.wait(5)
        job = BackgroundJob("t", work)
        self.assertIsNone(job.eta_seconds)
        job.start()
        wait_for(lambda: job.progress[0] == 1)
        time.sleep(0.02)
        self.assertGreater(job.eta_seconds, 0)
        gate.set()
        job.wait(5)
        self.assertIsNone(job.eta_seconds)


class SettingsFormTests(unittest.TestCase):
    def test_every_field_exists_in_settings_and_has_a_valid_default(self):
        data = Settings().to_dict()
        for field in ALL_FIELDS:
            self.assertIn(field.name, data[field.section], field.label)
        self.assertEqual(SettingsForm(Settings()).problems(), [])
        self.assertEqual(len(FIELD_BY_KEY), len(ALL_FIELDS))
        self.assertGreaterEqual(len(PAGES), 3)

    def test_stepping_clamps_and_cycles(self):
        form = SettingsForm(Settings())
        duration = FIELD_BY_KEY[("simulation", "duration")]
        form.adjust(duration, 1)
        self.assertEqual(form.value(duration), 660.0)
        form.set_value(duration, 60.0)
        form.adjust(duration, -1)
        self.assertEqual(form.value(duration), 60.0)  # clamped at the stepping limit
        scenario = FIELD_BY_KEY[("traffic", "scenario")]
        form.set_value(scenario, scenario.choices[-1])
        form.adjust(scenario, 1)
        self.assertEqual(form.value(scenario), scenario.choices[0])
        flag = FIELD_BY_KEY[("display", "show_statistics")]
        before = form.value(flag)
        form.adjust(flag, 1)
        self.assertEqual(form.value(flag), not before)
        seed = FIELD_BY_KEY[("traffic", "seed")]
        form.adjust(seed, 1)
        self.assertEqual(form.value(seed), 43)
        self.assertIsInstance(form.value(seed), int)

    def test_typed_values_are_checked(self):
        form = SettingsForm(Settings())
        seed = FIELD_BY_KEY[("traffic", "seed")]
        self.assertTrue(form.set_text(seed, " 1234 "))
        self.assertEqual(form.value(seed), 1234)
        self.assertFalse(form.set_text(seed, "12.5"))
        self.assertIn("whole number", form.problems()[0])
        self.assertFalse(form.set_text(seed, "abc"))
        with self.assertRaises(ConfigError):
            form.settings()
        self.assertTrue(form.set_text(seed, "7"))
        self.assertEqual(form.messages, {})
        rate = FIELD_BY_KEY[("rl", "learning_rate")]
        self.assertTrue(form.set_text(rate, "0,25"))  # decimal comma accepted
        self.assertEqual(form.value(rate), 0.25)

    def test_rule_violations_are_reported_in_plain_english_and_cannot_be_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.json"
            form = SettingsForm(Settings())
            form.set_value(FIELD_BY_KEY[("lights", "max_green")], 5.0)  # below fixed greens and min green
            problems = form.problems()
            self.assertTrue(problems)
            with self.assertRaises(ConfigError):
                form.save(path)
            self.assertFalse(path.exists())

    def test_save_writes_a_file_that_loads_back_and_clears_dirty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "s.json"
            form = SettingsForm(Settings())
            self.assertFalse(form.dirty)
            form.set_value(FIELD_BY_KEY[("traffic", "scenario")], "high")
            form.set_value(FIELD_BY_KEY[("display", "theme")], "light")
            self.assertTrue(form.dirty)
            saved = form.save(path)
            self.assertFalse(form.dirty)
            loaded = Settings.load(path)
            self.assertEqual(loaded, saved)
            self.assertEqual(loaded.traffic.scenario, "high")
            self.assertEqual(loaded.display.theme, "light")

    def test_revert_and_defaults(self):
        base = Settings().with_changes("traffic", seed=99)
        form = SettingsForm(base)
        form.set_value(FIELD_BY_KEY[("traffic", "seed")], 5)
        form.revert()
        self.assertEqual(form.value(FIELD_BY_KEY[("traffic", "seed")]), 99)
        self.assertFalse(form.dirty)
        form.reset_to_defaults()
        self.assertEqual(form.value(FIELD_BY_KEY[("traffic", "seed")]), Settings().traffic.seed)
        self.assertTrue(form.dirty)

    def test_unlisted_settings_survive_a_save(self):
        base = Settings().with_changes("simulation", max_speed_kmh=40.0)
        with tempfile.TemporaryDirectory() as tmp:
            form = SettingsForm(base)
            form.set_value(FIELD_BY_KEY[("traffic", "seed")], 3)
            self.assertEqual(form.save(Path(tmp) / "s.json").simulation.max_speed_kmh, 40.0)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.settings = settings_for(60.0, "rush_hour", 3, validation_every=0)

    def plan(self, **kw):
        base = dict(settings=self.settings, scenarios=["rush_hour"], episodes=4,
                    model_path=self.dir / "m.json")
        base.update(kw)
        return TrainingPlan(**base)

    def test_plan_problems(self):
        self.assertEqual(self.plan().problems(), [])
        self.assertTrue(self.plan(scenarios=[]).problems())
        self.assertTrue(self.plan(scenarios=["nope"]).problems())
        for bad in (0, -3, 10**9, True, 2.5):
            self.assertTrue(self.plan(episodes=bad).problems(), bad)
        self.assertTrue(self.plan(continue_training=True).problems())  # no model yet

    def test_training_saves_model_log_and_graphs(self):
        seen = []
        out = run_training(self.plan(episodes=5), self.dir / "csv", self.dir / "graphs",
                           on_episode=lambda st, total: seen.append((st.episode, total)))
        self.assertEqual(seen, [(i, 5) for i in range(1, 6)])
        self.assertTrue(out.saved and out.safe and out.model_path.is_file())
        self.assertEqual(out.episodes_done, 5)
        self.assertEqual(len(out.log_path.read_text(encoding="utf-8").splitlines()), 6)
        if importlib.util.find_spec("matplotlib") is None:
            return
        self.assertTrue(all(p.is_file() for p in out.graph_files) and out.graph_files)

    def test_refuses_to_replace_a_model_unless_confirmed(self):
        run_training(self.plan(episodes=2), self.dir / "c", self.dir / "g")
        before = (self.dir / "m.json").read_bytes()
        plan = self.plan(episodes=2)
        self.assertTrue(plan.would_replace_model)
        with self.assertRaises(ValueError):
            run_training(plan, self.dir / "c", self.dir / "g")
        self.assertEqual((self.dir / "m.json").read_bytes(), before)
        plan.replace_existing = True
        run_training(plan, self.dir / "c", self.dir / "g")

    def test_continue_training_adds_episodes(self):
        run_training(self.plan(episodes=3), self.dir / "c", self.dir / "g")
        run_training(self.plan(episodes=2, continue_training=True), self.dir / "c", self.dir / "g")
        data = json.loads((self.dir / "m.json").read_text(encoding="utf-8"))
        self.assertEqual(data["training"]["episodes"], 5)

    def test_stop_after_some_episodes_still_saves_a_consistent_model(self):
        flag = {"stop": False}

        def on_episode(stats, total):
            flag["stop"] = stats.episode >= 2
        out = run_training(self.plan(episodes=50), self.dir / "c", self.dir / "g",
                           on_episode=on_episode, should_stop=lambda: flag["stop"])
        self.assertTrue(out.stopped_early)
        self.assertEqual(out.episodes_done, 2)
        self.assertTrue(out.saved)

    def test_a_run_that_finished_no_episode_never_overwrites_the_model(self):
        from unittest import mock

        from training.trainer import Trainer, TrainingResult
        run_training(self.plan(episodes=2), self.dir / "c", self.dir / "g")
        before = (self.dir / "m.json").read_bytes()
        plan = self.plan(episodes=2, replace_existing=True)
        with mock.patch.object(Trainer, "train", lambda self, *a, **k: TrainingResult(agent=self.agent, stopped_early=True)):
            out = run_training(plan, self.dir / "c", self.dir / "g")
        self.assertFalse(out.saved)
        self.assertEqual(out.episodes_done, 0)
        self.assertEqual((self.dir / "m.json").read_bytes(), before)

    def test_a_stop_asked_for_at_once_ends_after_at_most_one_episode(self):
        out = run_training(self.plan(episodes=5), self.dir / "c", self.dir / "g", should_stop=lambda: True)
        self.assertEqual(out.episodes_done, 1)
        self.assertTrue(out.stopped_early)

    def test_runs_inside_a_background_job_with_pause_and_stop(self):
        def work(job):
            return run_training(self.plan(episodes=500), self.dir / "c", self.dir / "g",
                                on_episode=lambda st, total: job.report(st.episode, total),
                                should_stop=job.should_stop, wait_if_paused=job.wait_if_paused)
        job = BackgroundJob("train", work)
        job.start()
        self.assertTrue(wait_for(lambda: job.progress[0] >= 2))
        job.pause()
        time.sleep(0.3)
        frozen = job.progress[0]
        time.sleep(0.4)
        self.assertLessEqual(job.progress[0] - frozen, 1)
        job.resume()
        self.assertTrue(wait_for(lambda: job.progress[0] > frozen + 1))
        job.request_stop()
        self.assertTrue(job.wait(30))
        self.assertEqual(job.state, jobs.STOPPED)
        self.assertTrue(job.result.saved)
        self.assertLess(job.result.episodes_done, 500)


class ResultsDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        settings = settings_for(90.0, "low", 5)
        cls.result = run_experiment(settings, ["low", "high"], runs=3, agent=varied_agent(settings), tune=True)
        cls.folder = save_experiment(cls.result, cls.root, graphs=False)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_lists_valid_and_broken_folders_newest_first(self):
        (self.root / "experiment_20300101_000000_x").mkdir()
        bad = self.root / "experiment_20300102_000000_y"
        bad.mkdir()
        (bad / "experiment.json").write_text("{not json", encoding="utf-8")
        (self.root / "other_folder").mkdir()
        found = list_experiments(self.root)
        names = [e.name for e in found]
        self.assertEqual(names, sorted(names, reverse=True))
        self.assertNotIn("other_folder", names)
        by_name = {e.name: e for e in found}
        self.assertFalse(by_name["experiment_20300102_000000_y"].ok)
        self.assertIn("damaged", by_name["experiment_20300102_000000_y"].problem)
        self.assertIn("missing", by_name["experiment_20300101_000000_x"].problem)
        good = by_name[self.folder.name]
        self.assertTrue(good.ok)
        self.assertEqual((good.runs, good.scenarios), (3, ("low", "high")))

    def test_missing_root_gives_an_empty_list(self):
        self.assertEqual(list_experiments(self.root / "nowhere"), [])

    def test_scenario_view_matches_the_results(self):
        data = read_experiment(self.folder)
        self.assertEqual(scenario_names(data), ["low", "high"])
        view = scenario_view(data, "high")
        self.assertEqual(view.controllers, ["fixed", "fixed_tuned", "rl"])
        first = view.rows[0]
        mean = self.result.scenario("high").summary("fixed", "average_waiting_time_all").mean
        self.assertTrue(first.cells["fixed"].startswith(f"{mean:.1f}"))
        self.assertEqual(len(view.verdicts), 3)
        self.assertTrue(any("Same traffic for all controllers: yes" in n for n in view.notes))
        with self.assertRaises(ValueError):
            scenario_view(data, "nope")

    def test_rejects_things_that_are_not_experiments(self):
        d = self.root / "experiment_odd"
        d.mkdir()
        (d / "experiment.json").write_text(json.dumps([1, 2]), encoding="utf-8")
        with self.assertRaises(ValueError):
            read_experiment(d)

    def test_list_graphs(self):
        d = self.root / "g"
        (d / "graphs").mkdir(parents=True)
        for n in ("b.png", "a.png", "c.txt"):
            (d / "graphs" / n).write_bytes(b"x")
        self.assertEqual([p.name for p in list_graphs(d)], ["a.png", "b.png"])
        self.assertEqual(list_graphs(self.root / "zzz"), [])


if __name__ == "__main__":
    unittest.main()
