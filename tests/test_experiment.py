import random
import unittest
from unittest import mock

from agents.q_learning import QLearningAgent
from config.settings import Settings
from controllers.fixed_controller import FixedTimeController
from controllers.rl_controller import QLearningController
from controllers.tuning import tune_fixed_time
from environment.rl_env import NUM_ACTIONS
from evaluation.experiment import (
    FIXED,
    METRIC_BY_NAME,
    METRICS,
    RL,
    TUNED,
    RewardMeter,
    run_experiment,
)
from evaluation.metrics import improvement_percent
from evaluation.seeds import evaluation_seed, validation_seed
from simulation.runner import run_episode


def settings_for(duration=120.0, scenario="rush_hour", seed=5, **rl):
    return Settings().updated(simulation={"duration": duration},
                              traffic={"scenario": scenario, "seed": seed}, rl=rl)


def varied_agent(settings, seed=1):
    agent = QLearningAgent(settings.rl, seed=0)
    rng = random.Random(seed)
    for row in agent.q:
        row[:] = [rng.uniform(-5, 5) for _ in range(NUM_ACTIONS)]
    agent.episodes_trained = 7
    return agent


class RewardMeterTests(unittest.TestCase):
    def test_total_reward_matches_an_independent_calculation(self):
        settings = settings_for(duration=100.0, switch_penalty=3.0, queue_limit=4, queue_penalty=0.5)
        samples = {}

        def record(sim):
            samples[round(sim.time, 3)] = (sum(sim.queue_lengths().values()), sim.light.switch_count)

        meter = RewardMeter(settings.rl)

        def both(sim):
            record(sim)
            meter(sim)

        run_episode(settings, FixedTimeController(settings), seed=3, on_step=both)
        expected, (waiting, switches) = 0.0, samples[0.0]
        for t in range(5, 101, 5):
            now_waiting, now_switches = samples[float(t)]
            expected += ((waiting - now_waiting) - 3.0 * (now_switches - switches)
                         - 0.5 * max(0, now_waiting - 4))
            waiting, switches = now_waiting, now_switches
        self.assertGreater(len([s for s in samples.values() if s[1] > 0]), 0)  # a switch happened
        self.assertAlmostEqual(meter.total, expected)

    def test_the_last_partial_interval_is_counted(self):
        # no switches and no excess queue: the reward telescopes to (waiting at start - waiting at end),
        # which is only right if the final 2 s after the last 5 s mark are included
        quiet = settings_for(duration=47.0, scenario="low", switch_penalty=0.0, queue_penalty=0.0)
        meter, waiting = RewardMeter(quiet.rl), []
        run_episode(quiet, FixedTimeController(quiet), seed=3,
                    on_step=lambda sim: (waiting.append(sum(sim.queue_lengths().values())), meter(sim)))
        self.assertNotEqual(waiting[-1], waiting[-5])  # the last 2 s really changed the queue
        self.assertAlmostEqual(meter.total, waiting[0] - waiting[-1])


class TuningTests(unittest.TestCase):
    def test_tuned_is_never_worse_than_the_start_on_the_tuning_seeds(self):
        result = tune_fixed_time(settings_for(duration=200.0), runs=2, candidates=(10, 20, 30))
        self.assertLessEqual(result.score, result.start_score)
        self.assertEqual((result.start_ns_green, result.start_ew_green), (30.0, 30.0))
        self.assertEqual(len(result.tried), 9)  # 3 x 3 pairs; the start pair is among them
        self.assertEqual(result.score, min(score for _, _, score in result.tried))

    def test_candidates_outside_the_light_limits_are_ignored_and_the_start_is_kept(self):
        result = tune_fixed_time(settings_for(duration=100.0), runs=1, candidates=(5, 12, 90))
        pairs = {(a, b) for a, b, _ in result.tried}
        self.assertEqual(pairs, {(30.0, 30.0), (12.0, 12.0)})  # 5 and 90 are out of range
        self.assertNotIn(5.0, {a for a, _ in pairs})

    def test_a_tie_keeps_the_starting_pair(self):
        result = tune_fixed_time(settings_for(duration=60.0), runs=1, candidates=(30,))
        self.assertEqual((result.ns_green, result.ew_green), (30.0, 30.0))

    def test_tuning_uses_validation_seeds_never_evaluation_seeds(self):
        used = []
        real = run_episode

        def spy(settings, controller, seed=None, **kw):
            used.append(seed)
            return real(settings, controller, seed=seed, **kw)

        with mock.patch("controllers.tuning.run_episode", spy):
            tune_fixed_time(settings_for(duration=30.0, seed=9), runs=3, candidates=(10, 20))
        self.assertEqual(set(used), {validation_seed(9, k) for k in range(3)})
        self.assertFalse(set(used) & {evaluation_seed(9, k) for k in range(200)})

    def test_bad_arguments_and_progress(self):
        with self.assertRaises(ValueError):
            tune_fixed_time(settings_for(), runs=0)
        calls = []
        tune_fixed_time(settings_for(duration=30.0), runs=1, candidates=(10, 20),
                        on_progress=lambda d, t: calls.append((d, t)))
        self.assertEqual(calls[-1], (5, 5))  # 2 x 2 candidates plus the starting pair

    def test_the_tuned_times_are_valid_settings(self):
        result = tune_fixed_time(settings_for(duration=100.0, scenario="uneven"), runs=1)
        Settings().with_changes("fixed", ns_green=result.ns_green, ew_green=result.ew_green)


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.settings = settings_for(duration=120.0)
        self.agent = varied_agent(self.settings)
        self.result = run_experiment(self.settings, ["rush_hour", "low"], runs=4,
                                     agent=self.agent, tune_runs=1)

    def test_every_controller_runs_every_seed_of_every_scenario(self):
        self.assertEqual([s.scenario for s in self.result.scenarios], ["rush_hour", "low"])
        for scenario in self.result.scenarios:
            self.assertEqual(scenario.controllers, [FIXED, TUNED, RL])
            self.assertEqual(scenario.seeds, [evaluation_seed(5, k) for k in range(4)])
            for key in scenario.controllers:
                self.assertEqual([r.seed for r in scenario.records[key]], scenario.seeds)
                self.assertEqual([r.run for r in scenario.records[key]], [0, 1, 2, 3])

    def test_all_controllers_face_identical_traffic(self):
        for scenario in self.result.scenarios:
            self.assertTrue(scenario.traffic_was_identical())
            for k in range(4):
                arrived = {scenario.records[c][k].metrics.vehicles_arrived for c in scenario.controllers}
                self.assertEqual(len(arrived), 1, (scenario.scenario, k))

    def test_results_equal_running_the_controllers_directly(self):
        scenario = self.result.scenario("rush_hour")
        run = 2
        seed = scenario.seeds[run]
        s = self.settings.with_changes("traffic", scenario="rush_hour")
        direct = run_episode(s, FixedTimeController(s), seed=seed).metrics
        self.assertEqual(scenario.records[FIXED][run].metrics, direct)
        direct_rl = run_episode(s, QLearningController(self.agent), seed=seed).metrics
        self.assertEqual(scenario.records[RL][run].metrics, direct_rl)
        tuned = s.with_changes("fixed", ns_green=scenario.tuning.ns_green, ew_green=scenario.tuning.ew_green)
        self.assertEqual(scenario.records[TUNED][run].metrics,
                         run_episode(tuned, FixedTimeController(tuned), seed=seed).metrics)

    def test_the_default_controller_uses_the_settings_green_times(self):
        custom = self.settings.with_changes("fixed", ns_green=20.0, ew_green=25.0)
        result = run_experiment(custom, runs=2, tune=False, agent=None)
        scenario = result.scenarios[0]
        self.assertEqual(scenario.controllers, [FIXED])
        direct = run_episode(custom, FixedTimeController(custom), seed=scenario.seeds[0]).metrics
        self.assertEqual(scenario.records[FIXED][0].metrics, direct)

    def test_safety_and_model_information(self):
        for scenario in self.result.scenarios:
            self.assertEqual(scenario.safety_violations(), 0)
        self.assertEqual(self.result.model["episodes_trained"], 7)
        self.assertEqual(self.result.runs, 4)

    def test_improvement_follows_the_documented_formula(self):
        scenario = self.result.scenario("rush_hour")
        for name in ("average_waiting_time_all", "average_queue_length", "vehicles_served",
                     "throughput_per_minute"):
            info = METRIC_BY_NAME[name]
            c = scenario.compare(RL, FIXED, name)
            base = sum(scenario.values(FIXED, name)) / 4
            cand = sum(scenario.values(RL, name)) / 4
            self.assertAlmostEqual(c.base_mean, base)
            self.assertAlmostEqual(c.improvement_percent,
                                   improvement_percent(base, cand, info.lower_is_better))
            if info.lower_is_better:
                self.assertAlmostEqual(c.improvement_percent, (base - cand) / base * 100)
            else:
                self.assertAlmostEqual(c.improvement_percent, (cand - base) / base * 100)

    def test_total_reward_has_a_difference_but_no_percentage(self):
        c = self.result.scenario("low").compare(RL, FIXED, "total_reward")
        self.assertIsNone(c.improvement_percent)
        self.assertIsNotNone(c.paired.differences.mean)

    def test_the_time_series_are_averaged_over_the_runs(self):
        scenario = self.result.scenario("rush_hour")
        for key in scenario.controllers:
            series = scenario.series[key]
            self.assertGreater(len(series.times), 10)
            self.assertEqual(len(series.times), len(series.total_queue))
            self.assertEqual(len(series.times), len(series.average_wait_so_far))

    def test_all_metrics_exist_on_the_records(self):
        record = self.result.scenarios[0].records[FIXED][0]
        for info in METRICS:
            record.value(info.name)  # must not raise

    def test_options_leave_controllers_out(self):
        result = run_experiment(self.settings, runs=2, agent=None, tune=True, tune_runs=1)
        self.assertEqual(result.scenarios[0].controllers, [FIXED, TUNED])
        result = run_experiment(self.settings, runs=2, agent=self.agent, tune=False)
        self.assertEqual(result.scenarios[0].controllers, [FIXED, RL])
        self.assertIsNone(result.scenarios[0].tuning)

    def test_progress_and_stopping(self):
        calls = []
        run_experiment(self.settings, runs=3, agent=self.agent, tune=False,
                       on_progress=lambda d, t, text: calls.append((d, t, text)))
        self.assertEqual(calls[-1][:2], (6, 6))
        counter = {"n": 0}

        def stop():
            counter["n"] += 1
            return counter["n"] > 4

        partial = run_experiment(self.settings, runs=5, agent=self.agent, tune=False, should_stop=stop)
        self.assertTrue(partial.stopped_early)
        self.assertEqual(len(partial.scenarios[0].records[FIXED]), 4)
        self.assertNotIn(RL, [k for k, v in partial.scenarios[0].records.items() if v])

    def test_bad_arguments(self):
        for kwargs in ({"runs": 0}, {"runs": -1}, {"runs": 2.5}, {"runs": True}, {"runs": 1000},
                       {"runs": 2, "scenarios": ["nope"]}):
            with self.assertRaises(ValueError, msg=kwargs):
                run_experiment(self.settings, agent=None, tune=False, **kwargs)

    def test_same_inputs_give_identical_results(self):
        a = run_experiment(self.settings, runs=3, agent=self.agent, tune=False)
        b = run_experiment(self.settings, runs=3, agent=self.agent, tune=False)
        for key in (FIXED, RL):
            self.assertEqual([r.metrics for r in a.scenarios[0].records[key]],
                             [r.metrics for r in b.scenarios[0].records[key]])


if __name__ == "__main__":
    unittest.main()
