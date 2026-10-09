import csv
import random
import tempfile
import threading
import unittest
from pathlib import Path

from agents.q_learning import QLearningAgent
from config.settings import ConfigError, Settings
from controllers.rl_controller import QLearningController
from environment.rl_env import KEEP, SWITCH, TrafficEnv, all_states
from simulation.runner import run_episode
from evaluation.seeds import EVALUATION_SEED_OFFSET, evaluation_seed, training_seed, validation_seed
from training.trainer import CSV_COLUMNS, Trainer, rolling_mean


def make_settings(duration=120.0, scenario="rush_hour", seed=3, **rl):
    return Settings().updated(
        simulation={"duration": duration},
        traffic={"scenario": scenario, "seed": seed},
        rl=rl,
    )


class SeedTests(unittest.TestCase):
    def test_training_and_evaluation_seeds_do_not_overlap(self):
        train = {training_seed(42, i) for i in range(5000)}
        test = {evaluation_seed(42, i) for i in range(5000)}
        self.assertFalse(train & test)
        self.assertEqual(training_seed(42, 0), 42)
        self.assertEqual(evaluation_seed(42, 0), 42 + EVALUATION_SEED_OFFSET)

    def test_validation_seeds_are_separate_from_training_and_evaluation(self):
        train = {training_seed(42, i) for i in range(5000)}
        test = {evaluation_seed(42, i) for i in range(500)}
        valid = {validation_seed(42, i) for i in range(500)}
        self.assertFalse(valid & train)
        self.assertFalse(valid & test)

    def test_seeds_stay_in_range(self):
        from config.settings import MAX_SEED
        self.assertLessEqual(training_seed(MAX_SEED, 5), MAX_SEED)
        self.assertLessEqual(evaluation_seed(MAX_SEED, 5), MAX_SEED)

    def test_rolling_mean(self):
        self.assertEqual(rolling_mean([1, 2, 3, 4], 2), [1, 1.5, 2.5, 3.5])
        self.assertEqual(rolling_mean([None, 2, None], 2), [None, 2, 2])
        with self.assertRaises(ValueError):
            rolling_mean([1], 0)


class TrainingTests(unittest.TestCase):
    def test_plays_the_requested_episodes_and_records_each(self):
        settings = make_settings(epsilon=1.0, epsilon_decay=0.9, epsilon_min=0.1)
        result = Trainer(settings).train(6)
        self.assertEqual(result.episodes_done, 6)
        self.assertFalse(result.stopped_early)
        self.assertEqual([s.episode for s in result.stats], [1, 2, 3, 4, 5, 6])
        self.assertEqual([s.seed for s in result.stats], [training_seed(3, i) for i in range(6)])
        expected = [max(0.1, 0.9 ** i) for i in range(6)]
        for stats, eps in zip(result.stats, expected):
            self.assertAlmostEqual(stats.epsilon, eps)
        self.assertAlmostEqual(result.agent.epsilon, max(0.1, 0.9 ** 6))
        self.assertEqual(result.agent.episodes_trained, 6)
        self.assertGreater(result.agent.updates, 6 * 20)
        for stats in result.stats:
            self.assertEqual(stats.safety_violations, 0)
            self.assertTrue(15 <= stats.decisions <= 24, stats.decisions)  # 120 s / 5 s, fewer if it switches
            self.assertGreaterEqual(stats.vehicles_arrived, stats.vehicles_served)
            self.assertGreaterEqual(stats.q_table_change, 0)

    def test_default_episode_count_comes_from_the_settings(self):
        result = Trainer(make_settings(duration=30.0, episodes=4)).train()
        self.assertEqual(result.episodes_done, 4)

    def test_bad_episode_counts_are_refused(self):
        trainer = Trainer(make_settings())
        for bad in (0, -3, 2.5, True, "5"):
            with self.assertRaises(ValueError, msg=bad):
                trainer.train(bad)

    def test_same_settings_give_the_same_training(self):
        def run():
            result = Trainer(make_settings()).train(5)
            return [(s.total_reward, s.epsilon) for s in result.stats], result.agent.q
        self.assertEqual(run(), run())

    def test_learning_really_changes_the_table(self):
        result = Trainer(make_settings()).train(5)
        self.assertTrue(any(v != 0 for row in result.agent.q for v in row))
        self.assertTrue(any(v > 0 for row in result.agent.visits for v in row))

    def test_the_reward_improves_with_training(self):
        settings = make_settings(duration=300.0, seed=1)
        result = Trainer(settings).train(160)
        rewards = [s.total_reward for s in result.stats]
        first, last = sum(rewards[:40]) / 40, sum(rewards[-40:]) / 40
        self.assertGreater(last, first + 3, (first, last))

    def test_training_can_continue_from_where_it_stopped(self):
        trainer = Trainer(make_settings())
        trainer.train(3)
        epsilon = trainer.agent.epsilon
        again = trainer.train(2)
        self.assertEqual([s.episode for s in again.stats], [4, 5])
        self.assertAlmostEqual(again.stats[0].epsilon, epsilon)
        self.assertEqual(trainer.agent.episodes_trained, 5)

    def test_an_existing_agent_is_used(self):
        agent = QLearningAgent(make_settings().rl, seed=0)
        agent.episodes_trained = 10
        result = Trainer(make_settings(), agent).train(2)
        self.assertIs(result.agent, agent)
        self.assertEqual([s.episode for s in result.stats], [11, 12])

    def test_scenarios_are_cycled_and_checked(self):
        result = Trainer(make_settings(duration=30.0), scenarios=["low", "high", "uneven"]).train(7)
        self.assertEqual([s.scenario for s in result.stats],
                         ["low", "high", "uneven", "low", "high", "uneven", "low"])
        with self.assertRaises(ValueError):
            Trainer(make_settings(), scenarios=["low", "nonsense"])

    def test_the_progress_callback_sees_every_episode(self):
        seen = []
        Trainer(make_settings(duration=30.0)).train(4, on_episode=lambda s, total: seen.append((s.episode, total)))
        self.assertEqual(seen, [(1, 4), (2, 4), (3, 4), (4, 4)])

    def test_training_does_not_disturb_the_safety_rules(self):
        result = Trainer(make_settings(epsilon=1.0, epsilon_min=1.0)).train(8)  # pure random
        self.assertEqual(sum(s.safety_violations for s in result.stats), 0)


class ValidationTests(unittest.TestCase):
    def test_policy_is_checked_every_n_episodes_and_at_the_end(self):
        settings = make_settings(duration=60.0, validation_every=3, validation_runs=2)
        result = Trainer(settings).train(8)
        checked = [s.episode for s in result.stats if s.validation_waiting_time is not None]
        self.assertEqual(checked, [3, 6, 8])

    def test_validation_can_be_switched_off(self):
        result = Trainer(make_settings(duration=60.0, validation_every=0)).train(4)
        self.assertTrue(all(s.validation_waiting_time is None for s in result.stats))
        self.assertIsNone(result.best_episode)

    def test_the_best_policy_seen_is_the_one_kept(self):
        settings = make_settings(duration=120.0, validation_every=2, validation_runs=2)
        trainer = Trainer(settings)
        snapshots = {}

        def remember(stats, total):
            snapshots[stats.episode] = [row[:] for row in trainer.agent.q]

        result = trainer.train(10, on_episode=remember)
        scores = {s.episode: s.validation_waiting_time for s in result.stats
                  if s.validation_waiting_time is not None}
        best = min(scores, key=lambda e: (scores[e], e))  # earliest wins a tie
        self.assertEqual(result.best_episode, best)
        self.assertAlmostEqual(result.best_score, scores[best])
        self.assertEqual(trainer.agent.q, snapshots[best])

    def test_the_kept_policy_scores_what_validation_said(self):
        settings = make_settings(duration=120.0, validation_every=4, validation_runs=3)
        trainer = Trainer(settings)
        result = trainer.train(8)
        controller = QLearningController(trainer.agent)
        scores = [run_episode(settings, controller, seed=validation_seed(3, k)).metrics
                  .average_waiting_time_all for k in range(3)]
        self.assertAlmostEqual(sum(scores) / 3, result.best_score)

    def test_validation_does_not_change_how_the_agent_learns(self):
        """Validation uses its own simulations and must not touch exploration or counts."""
        def run(every):
            result = Trainer(make_settings(duration=60.0, validation_every=every)).train(6)
            return [(s.total_reward, s.epsilon, s.seed) for s in result.stats]
        self.assertEqual(run(0), run(2))

    def test_a_stopped_run_still_keeps_its_best_policy(self):
        trainer = Trainer(make_settings(duration=60.0, validation_every=2))
        result = trainer.train(40, on_episode=lambda s, t: trainer.stop() if s.episode == 5 else None)
        self.assertTrue(result.stopped_early)
        self.assertIn(result.best_episode, (2, 4))

    def test_validation_works_with_several_scenarios(self):
        settings = make_settings(duration=60.0, validation_every=3, validation_runs=3)
        result = Trainer(settings, scenarios=["low", "high"]).train(3)
        self.assertIsNotNone(result.stats[-1].validation_waiting_time)

    def test_settings_are_checked(self):
        for changes in ({"validation_every": -1}, {"validation_runs": 0}):
            with self.assertRaises(ConfigError, msg=changes):
                Settings().with_changes("rl", **changes)
        Settings().with_changes("rl", validation_every=0, validation_runs=1)


class CsvLogTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def read(self, path):
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def test_one_row_per_episode_with_the_documented_columns(self):
        path = self.dir / "logs" / "train.csv"
        result = Trainer(make_settings()).train(4, log_path=path)
        rows = self.read(path)
        self.assertEqual(len(rows), 4)
        self.assertEqual(tuple(rows[0]), CSV_COLUMNS)
        for row, stats in zip(rows, result.stats):
            self.assertEqual(int(row["episode"]), stats.episode)
            self.assertAlmostEqual(float(row["total_reward"]), stats.total_reward)
            self.assertAlmostEqual(float(row["epsilon"]), stats.epsilon)
            self.assertEqual(row["scenario"], "rush_hour")
        self.assertEqual(result.log_path, path)

    def test_rows_are_written_as_the_episodes_finish(self):
        path = self.dir / "train.csv"
        counts = []
        Trainer(make_settings(duration=30.0)).train(
            3, log_path=path, on_episode=lambda s, t: counts.append(len(self.read(path))))
        self.assertEqual(counts, [1, 2, 3])

    def test_missing_averages_are_left_empty_not_zero(self):
        path = self.dir / "train.csv"
        Trainer(make_settings(duration=1.0, scenario="low")).train(1, log_path=path)
        row = self.read(path)[0]
        self.assertEqual(row["vehicles_served"], "0")
        self.assertEqual(row["average_waiting_time"], "")

    def test_no_log_file_unless_asked(self):
        result = Trainer(make_settings(duration=30.0)).train(1)
        self.assertIsNone(result.log_path)
        self.assertEqual(list(self.dir.iterdir()), [])


class StopAndPauseTests(unittest.TestCase):
    def test_stop_ends_training_after_the_current_episode(self):
        trainer = Trainer(make_settings(duration=30.0))
        result = trainer.train(50, on_episode=lambda s, t: trainer.stop() if s.episode == 3 else None)
        self.assertEqual(result.episodes_done, 3)
        self.assertTrue(result.stopped_early)
        self.assertEqual(trainer.agent.episodes_trained, 3)
        self.assertTrue(trainer.stop_requested)

    def test_a_stopped_trainer_keeps_what_it_learned_and_can_train_again(self):
        trainer = Trainer(make_settings(duration=30.0))
        trainer.train(50, on_episode=lambda s, t: trainer.stop() if s.episode == 2 else None)
        q_after_stop = [row[:] for row in trainer.agent.q]
        self.assertTrue(any(v != 0 for row in q_after_stop for v in row))
        result = trainer.train(2)  # the stop request does not carry over
        self.assertEqual(result.episodes_done, 2)
        self.assertFalse(result.stopped_early)

    def test_the_log_is_complete_after_a_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.csv"
            trainer = Trainer(make_settings(duration=30.0))
            trainer.train(20, log_path=path, on_episode=lambda s, t: trainer.stop() if s.episode == 4 else None)
            with path.open(encoding="utf-8") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 4)

    def test_an_error_in_the_callback_closes_the_log_and_propagates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.csv"

            def boom(stats, total):
                raise RuntimeError("callback failed")
            with self.assertRaises(RuntimeError):
                Trainer(make_settings(duration=30.0)).train(5, log_path=path, on_episode=boom)
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 2)  # header + 1 row

    def test_pause_holds_training_until_resumed(self):
        trainer = Trainer(make_settings(duration=30.0))
        paused_at = threading.Event()
        done = []

        def on_episode(stats, total):
            if stats.episode == 2:
                trainer.pause()
                paused_at.set()

        worker = threading.Thread(target=lambda: done.append(trainer.train(6, on_episode=on_episode)), daemon=True)
        worker.start()
        self.assertTrue(paused_at.wait(10))
        self.assertTrue(trainer.paused)
        worker.join(0.4)
        self.assertTrue(worker.is_alive())  # really waiting
        self.assertEqual(trainer.agent.episodes_trained, 2)
        trainer.resume()
        worker.join(30)
        self.assertFalse(worker.is_alive())
        self.assertEqual(done[0].episodes_done, 6)

    def test_stop_wakes_a_paused_trainer(self):
        trainer = Trainer(make_settings(duration=30.0))
        paused = threading.Event()
        done = []

        def on_episode(stats, total):
            trainer.pause()
            paused.set()

        worker = threading.Thread(target=lambda: done.append(trainer.train(10, on_episode=on_episode)), daemon=True)
        worker.start()
        self.assertTrue(paused.wait(10))
        trainer.stop()
        worker.join(30)
        self.assertFalse(worker.is_alive())
        self.assertTrue(done[0].stopped_early)
        self.assertEqual(done[0].episodes_done, 1)


class ControllerTests(unittest.TestCase):
    def varied_agent(self, seed, settings=None):
        agent = QLearningAgent((settings or make_settings()).rl, seed=0)
        rng = random.Random(seed)
        for row in agent.q:
            row[:] = [rng.uniform(-5, 5), rng.uniform(-5, 5)]
        return agent

    def test_controller_makes_the_same_decisions_as_the_environment(self):
        """The trained agent must behave in a test exactly as it did in training,
        whatever the decision interval (shorter or longer than yellow + all-red)."""
        cases = ((1, "rush_hour", 5.0), (2, "uneven", 5.0), (3, "random", 5.0),
                 (4, "high", 3.0), (5, "rush_hour", 10.0), (6, "balanced", 12.5))
        for agent_seed, scenario, interval in cases:
            settings = make_settings(duration=600.0, scenario=scenario, decision_interval=interval)
            agent = self.varied_agent(agent_seed, settings)
            env = TrafficEnv(settings)
            state = env.reset(seed=11)
            while not env.done:
                action = agent.choose_action(state, env.valid_actions(), explore=False)
                state, _, _, _ = env.step(action)
            controller = QLearningController(agent)
            result = run_episode(settings, controller, seed=11)
            label = (scenario, interval)
            self.assertEqual(result.simulator.summary(), env.sim.summary(), label)
            self.assertGreater(env.sim.light.switch_count, 3, label)  # a real, active policy
            self.assertEqual(result.metrics.safety_violations, 0)

    def test_a_controller_only_decides_during_a_steady_green(self):
        settings = make_settings(duration=300.0)
        controller = QLearningController(self.varied_agent(4))
        from environment.enums import LightStage
        from simulation.simulator import Simulator
        sim = Simulator(settings)
        controller.reset()
        times = []
        while not sim.finished:
            before, stage = controller.decisions, sim.light.stage
            controller.act(sim)
            if controller.decisions != before:
                self.assertIs(stage, LightStage.GREEN)
                times.append(sim.time)
            sim.step()
        gaps = [b - a for a, b in zip(times, times[1:])]
        self.assertGreater(len(times), 20)
        self.assertGreaterEqual(min(gaps), 5.0 - 1e-9)  # never more often than the decision interval

    def test_the_agent_in_control_cannot_break_the_light(self):
        agent = QLearningAgent(make_settings().rl, seed=0)
        for row in agent.q:
            row[:] = [0.0, 9.0]  # always wants to switch
        settings = make_settings(duration=600.0)
        result = run_episode(settings, QLearningController(agent), seed=2)
        self.assertEqual(result.metrics.safety_violations, 0)
        lights = settings.lights
        cycle = lights.min_green + lights.yellow + lights.all_red
        self.assertLessEqual(result.simulator.light.switch_count, int(600 / cycle) + 1)

    def test_evaluation_does_not_learn(self):
        agent = self.varied_agent(5)
        before = ([r[:] for r in agent.q], [r[:] for r in agent.visits], agent.epsilon)
        run_episode(make_settings(duration=300.0), QLearningController(agent), seed=1)
        self.assertEqual(([r[:] for r in agent.q], [r[:] for r in agent.visits], agent.epsilon), before)

    def test_evaluation_is_repeatable_and_ignores_epsilon(self):
        agent = self.varied_agent(6)
        agent.epsilon = 1.0
        controller = QLearningController(agent)
        a = run_episode(make_settings(), controller, seed=8).metrics
        b = run_episode(make_settings(), controller, seed=8).metrics
        self.assertEqual(a, b)

    def test_an_untrained_agent_just_keeps_the_phase(self):
        settings = make_settings(duration=300.0)
        result = run_episode(settings, QLearningController(QLearningAgent(settings.rl)), seed=1)
        # only the maximum green (60 s) ever changes the light: 60 + 7 s per phase
        self.assertEqual(result.simulator.light.switch_count, 4)

    def test_describe_mentions_the_mode(self):
        agent = QLearningAgent(make_settings().rl)
        self.assertIn("epsilon 0", QLearningController(agent).describe())
        self.assertIn("exploring", QLearningController(agent, explore=True).describe())
        self.assertEqual(QLearningController(agent).name, "q-learning")

    def test_every_state_has_a_decision(self):
        agent = self.varied_agent(7)
        for state in all_states():
            self.assertIn(agent.choose_action(state, [KEEP, SWITCH], explore=False), (KEEP, SWITCH))


if __name__ == "__main__":
    unittest.main()
