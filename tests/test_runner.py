import unittest

from config.settings import ConfigError, Settings
from controllers.base import Controller
from controllers.fixed_controller import FixedTimeController
from environment.enums import ALL_DIRECTIONS
from simulation.runner import run_episode
from simulation.simulator import Simulator


class AlwaysSwitch(Controller):
    """A very different controller: asks for a switch at every single step."""

    name = "always-switch"

    def act(self, sim):
        sim.light.request_switch()


class DoNothing(Controller):
    """Never asks for anything; the light's own maximum-green rule runs it."""

    name = "do-nothing"

    def act(self, sim):
        pass


def make_settings(scenario="high", seed=11, duration=300.0):
    settings = Settings().with_changes("traffic", scenario=scenario, seed=seed)
    return settings.with_changes("simulation", duration=duration)


class RunEpisodeTests(unittest.TestCase):
    def test_returns_metrics_series_and_final_simulator(self):
        settings = make_settings()
        result = run_episode(settings, FixedTimeController(settings))
        self.assertEqual(result.metrics.controller, "fixed")
        self.assertEqual(result.metrics.scenario, "high")
        self.assertEqual(result.metrics.seed, 11)
        self.assertAlmostEqual(result.metrics.duration, 300.0)
        self.assertTrue(result.simulator.finished)
        self.assertGreater(len(result.series.times), 30)
        self.assertGreater(result.metrics.vehicles_served, 0)

    def test_seed_argument_overrides_the_setting_and_is_recorded(self):
        settings = make_settings()
        a = run_episode(settings, FixedTimeController(settings))
        b = run_episode(settings, FixedTimeController(settings), seed=999)
        self.assertEqual(b.metrics.seed, 999)
        self.assertNotEqual(a.metrics.vehicles_arrived, b.metrics.vehicles_arrived)
        same = run_episode(settings, FixedTimeController(settings), seed=11)
        self.assertEqual(same.metrics, a.metrics)

    def test_on_step_is_called_at_the_start_and_after_every_step(self):
        settings = make_settings(duration=20.0)
        times = []
        run_episode(settings, DoNothing(), on_step=lambda sim: times.append(sim.time))
        self.assertEqual(len(times), 40 + 1)
        self.assertEqual((times[0], times[-1]), (0.0, 20.0))

    def test_invalid_settings_are_refused(self):
        bad = Settings()
        bad.traffic.seed = -1
        with self.assertRaises(ConfigError):
            run_episode(bad, DoNothing())

    def test_the_controller_is_reset_before_each_run(self):
        calls = []

        class Recording(DoNothing):
            def reset(self):
                calls.append("reset")

        run_episode(make_settings(duration=5.0), Recording())
        self.assertEqual(calls, ["reset"])


class ReproducibilityTests(unittest.TestCase):
    def test_same_inputs_give_identical_results(self):
        settings = make_settings("random", seed=5)
        first = run_episode(settings, FixedTimeController(settings))
        second = run_episode(settings, FixedTimeController(settings))
        self.assertEqual(first.metrics, second.metrics)
        self.assertEqual(first.series, second.series)

    def test_a_reused_controller_gives_the_same_result_as_a_fresh_one(self):
        settings = make_settings(seed=2)
        controller = FixedTimeController(settings)
        first = run_episode(settings, controller)
        second = run_episode(settings, controller)
        self.assertEqual(first.metrics, second.metrics)


class FairnessTests(unittest.TestCase):
    """The comparison between controllers is only meaningful if the traffic is identical."""

    def arrivals(self, result):
        return [(v.id, v.direction, v.spawn_time, round(v.max_speed, 9))
                for v in result.simulator.all_vehicles()]

    def test_every_controller_faces_exactly_the_same_vehicles(self):
        for scenario in ("balanced", "uneven", "rush_hour", "random"):
            settings = make_settings(scenario, seed=21)
            runs = [run_episode(settings, c) for c in
                    (FixedTimeController(settings), AlwaysSwitch(), DoNothing())]
            reference = self.arrivals(runs[0])
            self.assertGreater(len(reference), 20)
            for other in runs[1:]:
                self.assertEqual(self.arrivals(other), reference, scenario)
                self.assertEqual(other.metrics.vehicles_arrived, runs[0].metrics.vehicles_arrived)

    def test_different_controllers_really_do_behave_differently(self):
        settings = make_settings(seed=21)
        fixed = run_episode(settings, FixedTimeController(settings)).metrics
        switchy = run_episode(settings, AlwaysSwitch()).metrics
        self.assertNotEqual(fixed.light_switches, switchy.light_switches)
        self.assertNotEqual(fixed.average_waiting_time, switchy.average_waiting_time)

    def test_every_controller_stays_safe(self):
        settings = make_settings("rush_hour", seed=8)
        for controller in (FixedTimeController(settings), AlwaysSwitch(), DoNothing()):
            self.assertEqual(run_episode(settings, controller).metrics.safety_violations, 0)


class MetricsAgainstIndependentCalculationTests(unittest.TestCase):
    """Re-measure the same run by hand and compare with the collector."""

    def test_collector_matches_a_hand_rolled_measurement(self):
        settings = make_settings("rush_hour", seed=3)
        metrics = run_episode(settings, FixedTimeController(settings)).metrics

        sim = Simulator(settings)
        controller = FixedTimeController(settings)
        queue_sum = steps = peak = 0
        while not sim.finished:
            controller.act(sim)
            sim.step()
            total = sum(sim.queue_lengths().values())
            queue_sum, steps, peak = queue_sum + total, steps + 1, max(peak, total)
        served = sim.completed
        everyone = sim.all_vehicles()

        self.assertEqual(metrics.vehicles_served, len(served))
        self.assertEqual(metrics.vehicles_arrived, len(everyone))
        self.assertAlmostEqual(metrics.average_queue_length, queue_sum / steps)
        self.assertEqual(metrics.max_queue_length, peak)
        self.assertAlmostEqual(metrics.average_waiting_time,
                               sum(v.waiting_time for v in served) / len(served))
        self.assertAlmostEqual(metrics.average_travel_time,
                               sum(v.travel_time for v in served) / len(served))
        self.assertAlmostEqual(metrics.throughput_per_minute, len(served) / (sim.time / 60))

    def test_vehicles_are_conserved(self):
        settings = make_settings("rush_hour", seed=9)
        for controller in (FixedTimeController(settings), AlwaysSwitch()):
            m = run_episode(settings, controller).metrics
            self.assertEqual(m.vehicles_arrived, m.vehicles_served + m.vehicles_unserved)

    def test_per_road_queues_add_up_to_the_total(self):
        settings = make_settings("uneven", seed=4)
        m = run_episode(settings, FixedTimeController(settings)).metrics
        self.assertEqual(set(m.average_queue_by_road), {d.value for d in ALL_DIRECTIONS})
        self.assertAlmostEqual(sum(m.average_queue_by_road.values()), m.average_queue_length)

    def test_the_busy_road_has_the_longest_queue_in_the_uneven_scenario(self):
        settings = make_settings("uneven", seed=4, duration=900)
        by_road = run_episode(settings, FixedTimeController(settings)).metrics.average_queue_by_road
        self.assertEqual(max(by_road, key=by_road.get), "north")

    def test_the_series_matches_the_collector_that_made_it(self):
        settings = make_settings(seed=6)
        result = run_episode(settings, FixedTimeController(settings), sample_interval=10.0)
        times = result.series.times
        self.assertEqual(times[:3], [0.5, 10.0, 20.0])
        self.assertEqual(len(times), len(result.series.total_queue))
        self.assertEqual(len(times), len(result.series.average_wait_so_far))


class SanityTests(unittest.TestCase):
    def test_more_traffic_means_longer_queues_and_waits_under_the_same_controller(self):
        results = {}
        for scenario in ("low", "medium", "high", "rush_hour"):
            settings = make_settings(scenario, seed=1, duration=900)
            results[scenario] = run_episode(settings, FixedTimeController(settings)).metrics
        queues = [results[s].average_queue_length for s in ("low", "medium", "high", "rush_hour")]
        waits = [results[s].average_waiting_time_all for s in ("low", "medium", "high", "rush_hour")]
        self.assertEqual(queues, sorted(queues))
        self.assertEqual(waits, sorted(waits))

    def test_waiting_time_never_exceeds_travel_time(self):
        settings = make_settings("rush_hour", seed=2)
        m = run_episode(settings, FixedTimeController(settings)).metrics
        self.assertLessEqual(m.average_waiting_time, m.average_travel_time)


if __name__ == "__main__":
    unittest.main()
