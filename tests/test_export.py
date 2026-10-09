import importlib.util
import csv
import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

from evaluation.experiment import FIXED, LABELS, METRICS, RL, TUNED, run_experiment
from evaluation.export import (
    COMPARISONS,
    experiment_folder,
    markdown_report,
    save_experiment,
    to_json_data,
)
from evaluation.formatting import format_experiment
from tests.test_experiment import settings_for, varied_agent

HAVE_MATPLOTLIB = importlib.util.find_spec("matplotlib") is not None

PNG = b"\x89PNG\r\n\x1a\n"


class ExportTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = settings_for(duration=120.0)
        cls.agent = varied_agent(cls.settings)
        cls.result = run_experiment(cls.settings, ["rush_hour", "low"], runs=3, agent=cls.agent,
                                    tune_runs=1)

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def read_csv(self, path):
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))


class FilesTests(ExportTestCase):
    def test_all_files_are_written_into_a_new_timestamped_folder(self):
        folder = save_experiment(self.result, self.root, graphs=False)
        self.assertEqual(folder.parent, self.root)
        self.assertRegex(folder.name, r"^experiment_\d{8}_\d{6}_rush_hour_low$")
        self.assertEqual(sorted(p.name for p in folder.iterdir()),
                         ["comparison.csv", "experiment.json", "runs.csv", "summary.csv", "summary.md"])

    def test_experiments_never_overwrite_each_other(self):
        first = save_experiment(self.result, self.root, graphs=False)
        second = save_experiment(self.result, self.root, graphs=False)
        self.assertNotEqual(first, second)
        self.assertTrue((first / "runs.csv").is_file() and (second / "runs.csv").is_file())
        self.assertEqual(experiment_folder(self.root, self.result).name[-2:], "_3")

    def test_many_scenarios_get_a_short_folder_name(self):
        many = run_experiment(self.settings.with_changes("simulation", duration=30.0),
                              ["low", "medium", "high", "balanced"], runs=1, agent=None, tune=False)
        self.assertIn("4_scenarios", experiment_folder(self.root, many).name)

    def test_runs_csv_has_one_row_per_controller_scenario_and_seed(self):
        folder = save_experiment(self.result, self.root, graphs=False)
        rows = self.read_csv(folder / "runs.csv")
        self.assertEqual(len(rows), 2 * 3 * 3)  # scenarios x controllers x runs
        self.assertEqual({r["controller"] for r in rows}, {FIXED, TUNED, RL})
        scenario = self.result.scenario("rush_hour")
        record = scenario.records[RL][1]
        row = next(r for r in rows if r["scenario"] == "rush_hour" and r["controller"] == RL and r["run"] == "1")
        self.assertEqual(int(row["seed"]), record.seed)
        self.assertEqual(int(row["vehicles_served"]), record.metrics.vehicles_served)
        self.assertAlmostEqual(float(row["average_waiting_time_all"]), record.metrics.average_waiting_time_all)
        self.assertAlmostEqual(float(row["total_reward"]), record.total_reward)

    def test_missing_values_are_empty_cells_not_zero(self):
        short = run_experiment(settings_for(duration=1.0, scenario="low"), runs=1, agent=None, tune=False)
        folder = save_experiment(short, self.root, graphs=False)
        row = self.read_csv(folder / "runs.csv")[0]
        self.assertEqual(row["average_waiting_time"], "")
        self.assertEqual(row["vehicles_served"], "0")

    def test_summary_and_comparison_csv(self):
        folder = save_experiment(self.result, self.root, graphs=False)
        summary = self.read_csv(folder / "summary.csv")
        self.assertEqual(len(summary), 2 * 3 * len(METRICS))
        row = next(r for r in summary if (r["scenario"], r["controller"], r["metric"]) ==
                   ("rush_hour", FIXED, "average_waiting_time_all"))
        s = self.result.scenario("rush_hour").summary(FIXED, "average_waiting_time_all")
        self.assertAlmostEqual(float(row["mean"]), s.mean)
        self.assertAlmostEqual(float(row["ci95_low"]), s.ci_low)
        comparison = self.read_csv(folder / "comparison.csv")
        self.assertEqual(len(comparison), 2 * len(COMPARISONS) * len(METRICS))
        waiting = next(r for r in comparison if (r["scenario"], r["candidate"], r["base"], r["metric"]) ==
                       ("rush_hour", RL, FIXED, "average_waiting_time_all"))
        c = self.result.scenario("rush_hour").compare(RL, FIXED, "average_waiting_time_all")
        self.assertAlmostEqual(float(waiting["improvement_percent"]), c.improvement_percent)
        self.assertIn(waiting["verdict"], ("better", "worse", "no clear difference"))
        reward = next(r for r in comparison if r["metric"] == "total_reward")
        self.assertEqual(reward["improvement_percent"], "")

    def test_json_holds_everything_and_can_be_read_back(self):
        folder = save_experiment(self.result, self.root, graphs=False)
        data = json.loads((folder / "experiment.json").read_text(encoding="utf-8"))
        self.assertEqual(data["runs_per_scenario"], 3)
        self.assertEqual(data["base_seed"], 5)
        self.assertEqual(data["model"]["episodes_trained"], 7)
        self.assertEqual(set(data["controllers"]), {FIXED, TUNED, RL})
        self.assertEqual(data["settings"]["simulation"]["duration"], 120.0)
        first = data["scenarios"][0]
        self.assertEqual(first["scenario"], "rush_hour")
        self.assertTrue(first["traffic_identical_for_all_controllers"])
        self.assertEqual(first["safety_violations"], 0)
        self.assertEqual(len(first["runs"]), 9)
        self.assertEqual(first["seeds"], self.result.scenario("rush_hour").seeds)
        self.assertIn("ns_green", first["tuning"])
        self.assertEqual(first["summary"][RL]["average_waiting_time_all"]["n"], 3)
        self.assertEqual(to_json_data(self.result)["scenarios"][1]["scenario"], "low")

    def test_results_without_rl_or_tuning_export_cleanly(self):
        plain = run_experiment(settings_for(duration=60.0), runs=2, agent=None, tune=False)
        folder = save_experiment(plain, self.root, graphs=False)
        data = json.loads((folder / "experiment.json").read_text(encoding="utf-8"))
        self.assertIsNone(data["model"])
        self.assertIsNone(data["scenarios"][0]["tuning"])
        self.assertEqual(data["scenarios"][0]["comparisons"], [])
        self.assertIn("Fixed-time (default)", (folder / "summary.md").read_text(encoding="utf-8"))


class ReportTests(ExportTestCase):
    def test_markdown_report_contents(self):
        text = markdown_report(self.result)
        for fragment in ("# Experiment results", "## Scenario: rush_hour", "## Scenario: low",
                         "Tuned fixed-time green times", "same traffic", "95 %", "Honest notes",
                         "Q-Learning model: trained 7 episodes"):
            self.assertIn(fragment, text)
        for label in LABELS.values():
            self.assertIn(label, text)
        self.assertIn("compared with", text)
        self.assertRegex(text, r"(better|worse|no clear difference) \(\d+/3 runs better\)")

    def test_reports_say_so_when_stopped_early(self):
        stopped = run_experiment(self.settings, runs=4, agent=None, tune=False, should_stop=lambda: True)
        self.assertIn("stopped early", markdown_report(stopped))

    def test_console_summary(self):
        lines = "\n".join(format_experiment(self.result))
        for fragment in ("Scenario rush_hour", "Scenario low", "Average waiting time", "Total reward",
                         "Q-Learning vs Fixed-time (default)", "same traffic for all controllers",
                         "safety conflicts 0"):
            self.assertIn(fragment, lines)


@unittest.skipUnless(HAVE_MATPLOTLIB, "matplotlib is not installed")
class GraphTests(ExportTestCase):
    def test_all_graphs_are_real_png_files(self):
        folder = save_experiment(self.result, self.root, graphs=True)
        graphs = {p.name: p for p in (folder / "graphs").iterdir()}
        for name in ("waiting_time_comparison.png", "queue_length_comparison.png",
                     "throughput_comparison.png", "rush_hour_waiting_over_time.png",
                     "rush_hour_vehicles_over_time.png", "low_waiting_over_time.png",
                     "low_vehicles_over_time.png"):
            self.assertIn(name, graphs)
        for path in graphs.values():
            data = path.read_bytes()
            self.assertTrue(data.startswith(PNG), path.name)
            self.assertGreater(len(data), 5_000, path.name)

    def test_graphs_have_titles_axis_labels_and_a_legend(self):
        import matplotlib.pyplot as plt

        from evaluation import graphs
        captured = []
        original = plt.close
        plt.close = lambda fig=None: captured.append(fig) or None
        try:
            graphs.bar_comparison(self.result, "average_waiting_time_all", "A title", "Seconds (s)",
                                  self.root / "a.png")
            graphs.over_time(self.result.scenario("low"), "vehicles_in_system", "Vehicles", "Count",
                             self.root / "b.png")
        finally:
            plt.close = original
        for fig in captured:
            ax = fig.axes[0]
            self.assertTrue(ax.get_title(loc="left"))
            self.assertTrue(ax.get_xlabel() and ax.get_ylabel())
            self.assertIsNotNone(ax.get_legend())
            self.assertGreaterEqual(len(ax.get_legend().get_texts()), 3)
            plt.close(fig)
        self.assertEqual(captured[0].axes[0].get_ylabel(), "Seconds (s)")

    def test_bars_show_the_real_means(self):
        import matplotlib.pyplot as plt

        from evaluation import graphs
        captured = []
        original = plt.close
        plt.close = lambda fig=None: captured.append(fig) or None
        try:
            graphs.bar_comparison(self.result, "average_waiting_time_all", "t", "y", self.root / "a.png")
        finally:
            plt.close = original
        ax = captured[0].axes[0]
        heights = sorted(round(p.get_height(), 6) for p in ax.patches)
        expected = sorted(round(s.summary(k, "average_waiting_time_all").mean, 6)
                          for s in self.result.scenarios for k in s.controllers)
        self.assertEqual(heights[:len(expected)], expected[:len(heights)] if len(heights) < len(expected) else expected)
        plt.close(captured[0])

    def test_training_graphs(self):
        from evaluation.graphs import save_training_graphs
        from training.trainer import Trainer
        stats = Trainer(settings_for(duration=30.0)).train(6).stats
        files = save_training_graphs(stats, self.root, "20260101_000000")
        self.assertEqual([f.name for f in files],
                         ["training_20260101_000000_reward.png", "training_20260101_000000_queue.png"])
        for f in files:
            self.assertTrue(f.read_bytes().startswith(PNG))
        self.assertEqual(save_training_graphs(stats[:1], self.root, "x"), [])


if __name__ == "__main__":
    unittest.main()
