import random
import unittest

from config.settings import SCENARIO_NAMES, ConfigError, RLConfig, Settings
from environment.enums import LightStage, Phase
from environment.rl_env import (
    ACTIONS,
    KEEP,
    NUM_ACTIONS,
    NUM_STATES,
    SWITCH,
    TrafficEnv,
    all_states,
    describe_state,
    encode_state,
    state_index,
    traffic_level,
)
from simulation.env_demo import run_env_demo
from simulation.simulator import Simulator


def make_settings(scenario="rush_hour", seed=5, duration=300.0, **rl):
    return Settings().updated(
        traffic={"scenario": scenario, "seed": seed},
        simulation={"duration": duration},
        rl=rl,
    )


def play(env, chooser, seed=None):
    """Play one whole episode; returns the list of (state, reward, info)."""
    env.reset(seed=seed)
    history = []
    while True:
        state, reward, done, info = env.step(chooser(env))
        history.append((state, reward, info))
        if done:
            return history


class StateTests(unittest.TestCase):
    def test_there_are_18_states_with_unique_indexes(self):
        states = all_states()
        self.assertEqual(len(states), NUM_STATES)
        self.assertEqual(NUM_STATES, 18)
        self.assertEqual([state_index(s) for s in states], list(range(18)))
        self.assertEqual(NUM_ACTIONS, 2)
        self.assertEqual(ACTIONS, (KEEP, SWITCH))

    def test_invalid_states_are_rejected(self):
        for bad in ((3, 0, 0), (0, -1, 0), (0, 0, 2), (0, 0, -1)):
            with self.assertRaises(ValueError, msg=bad):
                state_index(bad)
            with self.assertRaises(ValueError, msg=bad):
                describe_state(bad)

    def test_levels_follow_the_thresholds_exactly(self):
        rl = RLConfig(medium_traffic=5, high_traffic=12)
        expected = {0: 0, 4: 0, 5: 1, 11: 1, 12: 2, 40: 2}
        for count, level in expected.items():
            self.assertEqual(traffic_level(count, rl), level, count)
        rl = RLConfig(medium_traffic=2, high_traffic=3)
        self.assertEqual([traffic_level(n, rl) for n in range(5)], [0, 0, 1, 2, 2])

    def test_describe_state(self):
        self.assertEqual(describe_state((2, 0, 0)), "NS traffic high, EW traffic low, NS has green")
        self.assertEqual(describe_state((0, 1, 1)), "NS traffic low, EW traffic medium, EW has green")

    def test_state_reflects_the_simulator(self):
        settings = make_settings()
        sim = Simulator(settings)
        self.assertEqual(encode_state(sim, settings.rl), (0, 0, 0))
        sim.run(120)
        counts = sim.approach_counts()
        ns = counts[next(d for d in counts if d.phase is Phase.NS)]  # one road only
        state = encode_state(sim, settings.rl)
        busy_ns = sum(n for d, n in counts.items() if d.phase is Phase.NS)
        busy_ew = sum(n for d, n in counts.items() if d.phase is Phase.EW)
        self.assertEqual(state[0], traffic_level(busy_ns, settings.rl))
        self.assertEqual(state[1], traffic_level(busy_ew, settings.rl))
        self.assertEqual(state[2], 0 if sim.light.phase is Phase.NS else 1)
        self.assertGreaterEqual(busy_ns, ns)

    def test_starting_phase_is_in_the_state(self):
        settings = Settings().updated(lights={"initial_phase": "EW"})
        self.assertEqual(TrafficEnv(settings).get_state()[2], 1)


class SettingsTests(unittest.TestCase):
    def rejected(self, **changes):
        with self.assertRaises(ConfigError):
            Settings().with_changes("rl", **changes)

    def test_new_rl_settings_are_validated(self):
        self.rejected(medium_traffic=0)
        self.rejected(high_traffic=5, medium_traffic=5)
        self.rejected(high_traffic=3, medium_traffic=8)
        self.rejected(switch_penalty=-1.0)
        self.rejected(queue_limit=-1)
        self.rejected(queue_penalty=-0.1)
        Settings().with_changes("rl", medium_traffic=1, high_traffic=2, switch_penalty=0.0,
                                queue_limit=0, queue_penalty=0.0)


class EpisodeTests(unittest.TestCase):
    def test_reset_gives_a_fresh_valid_state(self):
        env = TrafficEnv(make_settings())
        state = env.reset()
        self.assertEqual(state, (0, 0, 0))
        self.assertEqual((env.sim.time, env.decisions, env.done), (0.0, 0, False))
        env.step(KEEP)
        env.step(KEEP)
        self.assertEqual(env.reset(), state)
        self.assertEqual((env.sim.time, env.decisions), (0.0, 0))

    def test_reset_seed_picks_the_traffic_and_repeats(self):
        env = TrafficEnv(make_settings())
        a = play(env, lambda e: KEEP, seed=11)
        b = play(env, lambda e: KEEP, seed=11)
        c = play(env, lambda e: KEEP, seed=12)
        self.assertEqual([(s, r) for s, r, _ in a], [(s, r) for s, r, _ in b])
        self.assertNotEqual([i["arrived"] for _, _, i in a], [i["arrived"] for _, _, i in c])
        self.assertEqual(env.seed, 12)

    def test_bad_actions_and_stepping_after_the_end(self):
        env = TrafficEnv(make_settings(duration=20.0))
        for bad in (2, -1, None, "KEEP", 0.5):
            with self.assertRaises(ValueError, msg=bad):
                env.step(bad)
        while not env.done:
            env.step(KEEP)
        with self.assertRaises(RuntimeError):
            env.step(KEEP)
        env.reset()
        env.step(KEEP)  # usable again

    def test_keep_runs_exactly_one_decision_interval(self):
        for interval in (2.0, 5.0, 8.0):
            env = TrafficEnv(make_settings(decision_interval=interval))
            _, _, _, info = env.step(KEEP)
            self.assertAlmostEqual(info["seconds"], interval)
            self.assertAlmostEqual(env.sim.time, interval)
            self.assertEqual(info["action"], "KEEP")
            self.assertFalse(info["switch_ignored"])

    def test_the_episode_ends_exactly_at_the_duration(self):
        env = TrafficEnv(make_settings(duration=57.0))
        history = play(env, lambda e: KEEP)
        self.assertTrue(env.done)
        self.assertAlmostEqual(env.sim.time, 57.0)
        self.assertEqual([i["decisions"] for _, _, i in history], list(range(1, len(history) + 1)))
        self.assertEqual(sum(1 for _, _, i in history if i["time"] < 57.0), len(history) - 1)

    def test_every_state_the_agent_sees_has_a_steady_green(self):
        env = TrafficEnv(make_settings())
        rng = random.Random(3)
        env.reset()
        while True:
            _, _, done, _ = env.step(rng.choice(env.valid_actions()))
            if done:
                break
            self.assertIs(env.sim.light.stage, LightStage.GREEN)
            self.assertAlmostEqual(env.sim.light.stage_time % 0.5, 0.0)


class SwitchingTests(unittest.TestCase):
    def test_switch_is_not_valid_until_the_minimum_green_has_passed(self):
        env = TrafficEnv(make_settings())  # min green 10 s, decisions every 5 s
        self.assertEqual(env.valid_actions(), [KEEP])
        env.step(KEEP)
        self.assertEqual(env.valid_actions(), [KEEP])
        env.step(KEEP)
        self.assertEqual(env.valid_actions(), [KEEP, SWITCH])

    def test_an_accepted_switch_changes_the_phase_after_yellow_and_all_red(self):
        env = TrafficEnv(make_settings())
        env.step(KEEP)
        env.step(KEEP)
        state, reward, done, info = env.step(SWITCH)
        self.assertFalse(info["switch_ignored"])
        self.assertEqual(env.sim.light.phase, Phase.EW)
        self.assertEqual(state[2], 1)
        self.assertEqual(env.sim.light.switch_count, 1)
        lights = env.sim.settings.lights
        self.assertAlmostEqual(info["seconds"], lights.yellow + lights.all_red)
        self.assertEqual(info["reward_parts"]["switching"], -env.rl.switch_penalty)

    def test_a_refused_switch_is_just_a_keep_and_is_not_punished(self):
        refused, kept = TrafficEnv(make_settings()), TrafficEnv(make_settings())
        r = refused.step(SWITCH)
        k = kept.step(KEEP)
        self.assertTrue(r.info["switch_ignored"])
        self.assertEqual(r.info["reward_parts"]["switching"], 0.0)
        self.assertEqual((r.state, r.reward, r.info["time"]), (k.state, k.reward, k.info["time"]))
        self.assertEqual(refused.sim.light.switch_count, 0)
        self.assertEqual(refused.sim.light.phase, Phase.NS)

    def test_the_agent_cannot_bypass_the_safety_rules(self):
        """Asking to switch at every opportunity still obeys minimum green and conflicts."""
        settings = make_settings(duration=900.0)
        env = TrafficEnv(settings)
        lights = settings.lights
        env.reset()
        change_times, last_phase = [], env.sim.light.phase
        while True:
            _, _, done, info = env.step(SWITCH)
            self.assertEqual(info["safety_violations"], 0)
            self.assertTrue(env.sim.light.is_conflict_free())
            if env.sim.light.phase is not last_phase:
                change_times.append(env.sim.time)
                last_phase = env.sim.light.phase
            if done:
                break
        self.assertGreater(len(change_times), 5)
        minimum = lights.min_green + lights.yellow + lights.all_red
        for earlier, later in zip(change_times, change_times[1:]):
            self.assertGreaterEqual(later - earlier, minimum - 1e-9)

    def test_staying_on_one_phase_is_ended_by_the_maximum_green(self):
        settings = make_settings(duration=300.0)
        env = TrafficEnv(settings)
        history = play(env, lambda e: KEEP)
        self.assertGreaterEqual(history[-1][2]["switches"], 3)  # forced by max green (60 s)
        self.assertEqual(history[-1][2]["safety_violations"], 0)


class RewardTests(unittest.TestCase):
    def test_reward_is_the_reduction_in_waiting_when_nothing_else_applies(self):
        env = TrafficEnv(make_settings(switch_penalty=0.0, queue_penalty=0.0))
        env.reset()
        for _ in range(30):
            before = env.waiting_vehicles()
            _, reward, done, info = env.step(KEEP)
            self.assertEqual(reward, before - env.waiting_vehicles())
            self.assertEqual(info["reward_parts"]["switching"], 0.0)
            if done:
                break

    def test_reward_formula_matches_a_hand_calculation(self):
        env = TrafficEnv(make_settings(switch_penalty=3.0, queue_limit=4, queue_penalty=0.5))
        env.reset()
        saw_excess = saw_switch = False
        rng = random.Random(1)
        while True:
            before_waiting = env.waiting_vehicles()
            before_switches = env.sim.light.switch_count
            _, reward, done, info = env.step(rng.choice(env.valid_actions()))
            after_waiting = env.waiting_vehicles()
            switches = env.sim.light.switch_count - before_switches
            expected = ((before_waiting - after_waiting) - 3.0 * switches
                        - 0.5 * max(0, after_waiting - 4))
            self.assertAlmostEqual(reward, expected)
            parts = info["reward_parts"]
            self.assertAlmostEqual(parts["reduction"] + parts["switching"] + parts["excess"],
                                   parts["total"])
            self.assertAlmostEqual(env.calculate_reward(), reward)
            saw_excess |= parts["excess"] < 0
            saw_switch |= switches > 0
            if done:
                break
        self.assertTrue(saw_excess and saw_switch)  # the test really exercised both penalties

    def test_waiting_counts_vehicles_outside_a_full_road_too(self):
        env = TrafficEnv(make_settings(scenario="rush_hour", duration=600.0))
        env.reset()
        while not env.done:
            env.step(KEEP)
            outside = sum(len(r.backlog) for r in env.sim.roads.values())
            self.assertGreaterEqual(env.waiting_vehicles(), outside)
        self.assertEqual(env.waiting_vehicles(), sum(env.sim.queue_lengths().values()))

    def test_total_reward_without_penalties_is_start_minus_end_waiting(self):
        env = TrafficEnv(make_settings(switch_penalty=0.0, queue_penalty=0.0))
        history = play(env, lambda e: KEEP)
        self.assertEqual(sum(r for _, r, _ in history), 0 - env.waiting_vehicles())


class SafetyAndFairnessTests(unittest.TestCase):
    def test_random_agent_completes_every_scenario_safely(self):
        for scenario in SCENARIO_NAMES:
            settings = make_settings(scenario=scenario, duration=400.0)
            env = TrafficEnv(settings)
            rng = random.Random(4)
            history = play(env, lambda e: rng.choice(e.valid_actions()), seed=2)
            sim = env.sim
            self.assertTrue(env.done, scenario)
            self.assertEqual(sim.safety_violations, 0, scenario)
            self.assertEqual(sim.spawned, len(sim.completed) + sim.vehicles_in_system(), scenario)
            metrics = env.episode_metrics()
            self.assertEqual(metrics.safety_violations, 0)
            self.assertEqual(metrics.vehicles_arrived, history[-1][2]["arrived"])
            self.assertEqual(metrics.vehicles_served, history[-1][2]["served"])
            for state, _, _ in history:
                state_index(state)  # always a legal state

    def test_same_seed_and_agent_give_identical_episodes(self):
        def run():
            env = TrafficEnv(make_settings())
            rng = random.Random(9)
            return [(s, r) for s, r, _ in play(env, lambda e: rng.choice(e.valid_actions()), seed=6)]
        self.assertEqual(run(), run())

    def test_the_agent_cannot_change_which_vehicles_arrive(self):
        settings = make_settings(scenario="high", duration=300.0)
        keep_env, switch_env = TrafficEnv(settings), TrafficEnv(settings)
        play(keep_env, lambda e: KEEP, seed=3)
        play(switch_env, lambda e: SWITCH, seed=3)

        def arrivals(env):
            return [(v.id, v.direction, v.spawn_time) for v in env.sim.all_vehicles()]
        self.assertEqual(arrivals(keep_env), arrivals(switch_env))
        self.assertNotEqual(keep_env.sim.light.switch_count, switch_env.sim.light.switch_count)

    def test_snapshot_tracks_what_the_brief_asks_for(self):
        env = TrafficEnv(make_settings())
        env.step(KEEP)
        snap = env.snapshot()
        for key in ("time", "phase", "waiting", "queues", "served", "arrived", "switches",
                    "decisions", "safety_violations"):
            self.assertIn(key, snap)
        self.assertEqual(snap["time"], 5.0)
        self.assertEqual(snap["decisions"], 1)
        self.assertEqual(snap["waiting"], sum(snap["queues"].values()))


class DemoTests(unittest.TestCase):
    def test_env_demo_runs_and_reports(self):
        lines = []
        result = run_env_demo(make_settings(duration=120.0), episodes=2, print_fn=lines.append)
        text = "\n".join(lines)
        self.assertEqual(result.episodes, 2)
        self.assertEqual(len(result.returns), 2)
        self.assertEqual(result.safety_violations, 0)
        self.assertGreater(result.decisions, 40)
        self.assertIn("does NOT learn", text)
        self.assertIn("PASSED", text)

    def test_env_demo_rejects_zero_episodes(self):
        with self.assertRaises(ValueError):
            run_env_demo(make_settings(), episodes=0, print_fn=lambda _: None)


if __name__ == "__main__":
    unittest.main()
