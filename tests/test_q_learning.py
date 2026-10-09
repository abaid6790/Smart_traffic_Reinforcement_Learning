import json
import math
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agents.q_learning import MODEL_FORMAT, MODEL_VERSION, ModelError, QLearningAgent
from config.settings import RLConfig
from environment.rl_env import KEEP, NUM_ACTIONS, NUM_STATES, SWITCH, all_states, state_index

S, NEXT = (1, 2, 0), (0, 1, 1)


def agent_with(**changes):
    return QLearningAgent(RLConfig(**changes), seed=1)


class QTableTests(unittest.TestCase):
    def test_a_new_agent_knows_nothing(self):
        agent = agent_with()
        self.assertEqual(len(agent.q), NUM_STATES)
        self.assertTrue(all(row == [0.0] * NUM_ACTIONS for row in agent.q))
        self.assertEqual(agent.epsilon, RLConfig().epsilon)
        for state in all_states():
            for action in (KEEP, SWITCH):
                self.assertEqual(agent.get_q_value(state, action), 0.0)

    def test_get_q_value_rejects_bad_input(self):
        agent = agent_with()
        for state, action in (((3, 0, 0), KEEP), (S, 2), (S, -1), (S, True), (S, None)):
            with self.assertRaises(ValueError, msg=(state, action)):
                agent.get_q_value(state, action)

    def test_invalid_settings_are_refused(self):
        with self.assertRaises(ValueError):
            QLearningAgent(RLConfig(learning_rate=0.0))

    def test_update_follows_the_q_learning_rule(self):
        agent = agent_with(learning_rate=0.5, discount_factor=0.9)
        agent.q[state_index(NEXT)] = [3.0, 10.0]
        error = agent.update(S, KEEP, 2.0, NEXT)
        self.assertAlmostEqual(error, 2.0 + 0.9 * 10.0 - 0.0)
        self.assertAlmostEqual(agent.get_q_value(S, KEEP), 0.5 * 11.0)
        self.assertEqual(agent.get_q_value(S, SWITCH), 0.0)  # nothing else changed
        # a second update moves it from its new value
        agent.update(S, KEEP, 2.0, NEXT)
        self.assertAlmostEqual(agent.get_q_value(S, KEEP), 5.5 + 0.5 * (11.0 - 5.5))
        self.assertEqual(agent.visits[state_index(S)], [2, 0])
        self.assertEqual(agent.updates, 2)

    def test_terminal_updates_ignore_the_future(self):
        agent = agent_with(learning_rate=1.0, discount_factor=0.9)
        agent.q[state_index(NEXT)] = [50.0, 50.0]
        agent.update(S, SWITCH, -4.0, NEXT, terminal=True)
        self.assertAlmostEqual(agent.get_q_value(S, SWITCH), -4.0)

    def test_the_best_future_action_only_counts_valid_actions(self):
        agent = agent_with(learning_rate=1.0, discount_factor=0.5)
        agent.q[state_index(NEXT)] = [1.0, 100.0]
        agent.update(S, KEEP, 0.0, NEXT, next_valid_actions=[KEEP])
        self.assertAlmostEqual(agent.get_q_value(S, KEEP), 0.5)
        agent.update(S, SWITCH, 0.0, NEXT)  # all actions valid
        self.assertAlmostEqual(agent.get_q_value(S, SWITCH), 50.0)

    def test_update_rejects_bad_numbers(self):
        agent = agent_with()
        for reward in (math.nan, math.inf, -math.inf):
            with self.assertRaises(ValueError):
                agent.update(S, KEEP, reward, NEXT)
        with self.assertRaises(ValueError):
            agent.update(S, 5, 1.0, NEXT)
        with self.assertRaises(ValueError):
            agent.update(S, KEEP, 1.0, (9, 9, 9))
        self.assertEqual(agent.updates, 0)

    def test_the_rule_converges_to_the_true_value(self):
        # reward 1 forever, discount 0.5 -> value 1 / (1 - 0.5) = 2
        agent = agent_with(learning_rate=0.2, discount_factor=0.5)
        for _ in range(300):
            agent.update(S, KEEP, 1.0, S)
        self.assertAlmostEqual(agent.get_q_value(S, KEEP), 2.0, places=3)


class ActionChoiceTests(unittest.TestCase):
    def test_best_action_and_ties(self):
        agent = agent_with()
        self.assertEqual(agent.best_action(S), KEEP)  # tie goes to KEEP
        agent.q[state_index(S)] = [1.0, 2.0]
        self.assertEqual(agent.best_action(S), SWITCH)
        self.assertEqual(agent.best_action(S, [KEEP]), KEEP)  # SWITCH not allowed now
        agent.q[state_index(S)] = [2.0, 1.0]
        self.assertEqual(agent.best_action(S), KEEP)

    def test_random_tie_breaking_uses_both_actions(self):
        agent = agent_with()
        picks = {agent.best_action(S, break_ties_randomly=True) for _ in range(60)}
        self.assertEqual(picks, {KEEP, SWITCH})

    def test_without_exploration_epsilon_is_ignored(self):
        agent = agent_with(epsilon=1.0)
        agent.q[state_index(S)] = [0.0, 5.0]
        self.assertEqual({agent.choose_action(S, explore=False) for _ in range(100)}, {SWITCH})

    def test_epsilon_zero_is_purely_greedy_and_epsilon_one_is_random(self):
        agent = agent_with(epsilon=0.0, epsilon_min=0.0)
        agent.q[state_index(S)] = [5.0, 0.0]
        self.assertEqual({agent.choose_action(S) for _ in range(100)}, {KEEP})
        agent = agent_with(epsilon=1.0)
        agent.q[state_index(S)] = [5.0, 0.0]
        picks = [agent.choose_action(S) for _ in range(400)]
        self.assertGreater(picks.count(SWITCH), 120)
        self.assertGreater(picks.count(KEEP), 120)

    def test_exploration_rate_matches_epsilon(self):
        agent = agent_with(epsilon=0.3)
        agent.q[state_index(S)] = [5.0, 0.0]  # greedy = KEEP; random = KEEP half the time
        picks = [agent.choose_action(S) for _ in range(4000)]
        switch_rate = picks.count(SWITCH) / len(picks)
        self.assertAlmostEqual(switch_rate, 0.3 * 0.5, delta=0.03)

    def test_exploring_never_picks_an_invalid_action(self):
        agent = agent_with(epsilon=1.0)
        self.assertEqual({agent.choose_action(S, [KEEP]) for _ in range(100)}, {KEEP})
        with self.assertRaises(ValueError):
            agent.choose_action(S, [])

    def test_same_seed_same_choices(self):
        def run():
            agent = QLearningAgent(RLConfig(epsilon=0.6), seed=7)
            return [agent.choose_action(S) for _ in range(50)]
        self.assertEqual(run(), run())

    def test_epsilon_decays_to_its_floor(self):
        agent = agent_with(epsilon=1.0, epsilon_decay=0.5, epsilon_min=0.2)
        seen = [agent.decay_epsilon() for _ in range(4)]
        self.assertEqual(seen, [0.5, 0.25, 0.2, 0.2])

    def test_reset_forgets_everything(self):
        agent = agent_with(epsilon=0.8)
        agent.update(S, KEEP, 3.0, NEXT)
        agent.decay_epsilon()
        agent.episodes_trained = 9
        agent.reset()
        self.assertTrue(all(row == [0.0, 0.0] for row in agent.q))
        self.assertTrue(all(row == [0, 0] for row in agent.visits))
        self.assertEqual((agent.epsilon, agent.episodes_trained, agent.updates), (0.8, 0, 0))

    def test_policy_table(self):
        agent = agent_with()
        agent.update(S, SWITCH, 5.0, S)
        rows = agent.policy_table()
        self.assertEqual(len(rows), NUM_STATES)
        by_state = {r["state"]: r for r in rows}
        self.assertEqual(by_state[S]["best"], "SWITCH")
        self.assertEqual(by_state[(0, 0, 0)]["best"], "(never visited)")
        self.assertIn("NS traffic medium", by_state[(1, 0, 0)]["description"])


class ModelFileTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.path = self.dir / "model.json"

    def trained_agent(self):
        agent = QLearningAgent(RLConfig(learning_rate=0.3), seed=2)
        rng = random.Random(0)
        for _ in range(200):
            s, n = rng.choice(all_states()), rng.choice(all_states())
            agent.update(s, rng.choice((KEEP, SWITCH)), rng.uniform(-5, 5), n)
        agent.episodes_trained = 12
        agent.epsilon = 0.37
        return agent

    def edit(self, change):
        data = json.loads(self.path.read_text(encoding="utf-8"))
        change(data)
        self.path.write_text(json.dumps(data), encoding="utf-8")

    def test_save_then_load_gives_the_same_agent(self):
        agent = self.trained_agent()
        agent.save(self.path, scenarios=["rush_hour"], base_seed=5)
        loaded = QLearningAgent.load(self.path, RLConfig())
        self.assertEqual(loaded.q, agent.q)
        self.assertEqual(loaded.visits, agent.visits)
        self.assertEqual((loaded.episodes_trained, loaded.updates), (12, 200))
        self.assertAlmostEqual(loaded.epsilon, 0.37)
        for state in all_states():  # same decisions
            self.assertEqual(loaded.best_action(state), agent.best_action(state))

    def test_the_file_holds_metadata(self):
        self.trained_agent().save(self.path, scenarios=["low", "high"], base_seed=5)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual((data["format"], data["version"]), (MODEL_FORMAT, MODEL_VERSION))
        self.assertEqual(data["training"]["episodes"], 12)
        self.assertEqual(data["training"]["scenarios"], ["low", "high"])
        self.assertEqual(data["parameters"]["learning_rate"], 0.3)
        self.assertIn("discount_factor", data["parameters"])
        self.assertRegex(data["saved_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d")
        self.assertEqual(data["state_design"]["num_states"], NUM_STATES)
        self.assertEqual(QLearningAgent.load(self.path).info["training"]["base_seed"], 5)

    def test_saving_creates_folders_and_leaves_no_temporary_file(self):
        target = self.dir / "a" / "b" / "model.json"
        self.trained_agent().save(target)
        self.assertTrue(target.is_file())
        self.assertEqual([p.name for p in target.parent.iterdir()], ["model.json"])

    def test_a_failed_save_keeps_the_old_model(self):
        good = self.trained_agent()
        good.save(self.path)
        before = self.path.read_text(encoding="utf-8")
        other = QLearningAgent(RLConfig())
        with mock.patch("agents.q_learning.os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                other.save(self.path)
        self.assertEqual(self.path.read_text(encoding="utf-8"), before)
        self.assertEqual([p.name for p in self.dir.iterdir()], ["model.json"])

    def test_loading_problems_give_plain_messages(self):
        self.trained_agent().save(self.path)
        cases = {
            "not json": lambda: self.path.write_text("{oops", encoding="utf-8"),
            "list": lambda: self.path.write_text("[1, 2]", encoding="utf-8"),
            "binary": lambda: self.path.write_bytes(b"\xff\xfe\x00bad"),
            "other format": lambda: self.edit(lambda d: d.update(format="something else")),
            "old version": lambda: self.edit(lambda d: d.update(version=99)),
            "no q table": lambda: self.edit(lambda d: d.pop("q_table")),
            "no training": lambda: self.edit(lambda d: d.pop("training")),
            "no episodes": lambda: self.edit(lambda d: d["training"].pop("episodes")),
            "negative episodes": lambda: self.edit(lambda d: d["training"].update(episodes=-1)),
            "string episodes": lambda: self.edit(lambda d: d["training"].update(episodes="12")),
            "training not a group": lambda: self.edit(lambda d: d.update(training=5)),
            "too few rows": lambda: self.edit(lambda d: d["q_table"].pop()),
            "wrong row length": lambda: self.edit(lambda d: d["q_table"][0].append(1.0)),
            "text value": lambda: self.edit(lambda d: d["q_table"][3].__setitem__(0, "x")),
            "bool value": lambda: self.edit(lambda d: d["q_table"][3].__setitem__(0, True)),
            "negative visits": lambda: self.edit(lambda d: d["visits"][2].__setitem__(1, -4)),
            "fractional visits": lambda: self.edit(lambda d: d["visits"][2].__setitem__(1, 1.5)),
        }
        for name, damage in cases.items():
            self.trained_agent().save(self.path)
            damage()
            with self.assertRaises(ModelError, msg=name) as caught:
                QLearningAgent.load(self.path)
            self.assertNotIn("Traceback", str(caught.exception), name)
            self.assertIn("model", str(caught.exception).lower() + self.path.name, name)

    def test_not_a_number_values_are_refused(self):
        for bad in (math.nan, math.inf):
            self.trained_agent().save(self.path)
            self.edit(lambda d: d["q_table"][5].__setitem__(1, bad))  # json writes NaN / Infinity
            with self.assertRaises(ModelError) as caught:
                QLearningAgent.load(self.path)
            self.assertIn("contains", str(caught.exception))

    def test_missing_file(self):
        with self.assertRaises(ModelError) as caught:
            QLearningAgent.load(self.dir / "nothing.json")
        self.assertIn("not found", str(caught.exception))

    def test_a_model_for_a_different_state_design_is_refused(self):
        self.trained_agent().save(self.path)
        for changes in ({"medium_traffic": 6}, {"high_traffic": 15}, {"decision_interval": 10.0}):
            with self.assertRaises(ModelError, msg=changes) as caught:
                QLearningAgent.load(self.path, RLConfig(**changes))
            self.assertIn("state design", str(caught.exception))
        # learning parameters are free to differ; they only matter while training
        QLearningAgent.load(self.path, RLConfig(learning_rate=0.9, epsilon_decay=0.9))


if __name__ == "__main__":
    unittest.main()
