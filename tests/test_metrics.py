import dataclasses
import json
import unittest

from config.settings import Settings
from environment.enums import Direction
from environment.vehicle import Vehicle
from evaluation.formatting import format_metrics
from evaluation.metrics import (
    HIGHER_IS_BETTER,
    LOWER_IS_BETTER,
    EpisodeMetrics,
    MetricsCollector,
    compare_metrics,
    improvement_percent,
)
from simulation.simulator import Simulator

N, S, E, W = Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST


def vehicle(vid, wait, travel, stops, direction=N, completed=True):
    return Vehicle(id=vid, direction=direction, max_speed=10.0, length=4.5,
                   waiting_time=wait, travel_time=travel, stops=stops, completed=completed)


def queues(n=0, s=0, e=0, w=0):
    return {N: n, S: s, E: e, W: w}


def hand_made_run():
    """A tiny run whose correct answers can be worked out by hand.

    Served:   A (wait 10, travel 40, 1 stop)  B (wait 20, travel 50, 2 stops)
              C (wait  0, travel 30, 0 stops)
    Unserved: D (wait 60, travel 70, 3 stops), still waiting to enter
    Queue totals over three steps: 10, 2 and 3.   Simulated time: 600 s.
    """
    sim = Simulator(Settings())
    sim.time = 600.0
    sim.spawned = 4
    sim.completed = [vehicle(1, 10, 40, 1), vehicle(2, 20, 50, 2), vehicle(3, 0, 30, 0)]
    sim.roads[W].backlog.append(vehicle(4, 60, 70, 3, W, completed=False))
    collector = MetricsCollector()
    collector.record_values(0.5, queues(n=1, s=2, e=3, w=4), 7)
    collector.record_values(1.0, queues(e=2), 5)
    collector.record_values(1.5, queues(n=3), 4)
    return sim, collector


class FormulaTests(unittest.TestCase):
    def setUp(self):
        sim, collector = hand_made_run()
        self.m = collector.result(sim, "test")

    def test_counts(self):
        self.assertEqual((self.m.vehicles_arrived, self.m.vehicles_served, self.m.vehicles_unserved), (4, 3, 1))

    def test_average_waiting_time_uses_served_vehicles(self):
        self.assertAlmostEqual(self.m.average_waiting_time, (10 + 20 + 0) / 3)

    def test_average_waiting_time_all_includes_vehicles_still_waiting(self):
        self.assertAlmostEqual(self.m.average_waiting_time_all, (10 + 20 + 0 + 60) / 4)
        self.assertGreater(self.m.average_waiting_time_all, self.m.average_waiting_time)

    def test_max_waiting_time_includes_unserved_vehicles(self):
        self.assertEqual(self.m.max_waiting_time, 60)

    def test_queue_statistics(self):
        self.assertAlmostEqual(self.m.average_queue_length, (10 + 2 + 3) / 3)
        self.assertEqual(self.m.max_queue_length, 10)

    def test_average_queue_by_road(self):
        by_road = self.m.average_queue_by_road
        self.assertAlmostEqual(by_road["north"], (1 + 0 + 3) / 3)
        self.assertAlmostEqual(by_road["south"], 2 / 3)
        self.assertAlmostEqual(by_road["east"], (3 + 2) / 3)
        self.assertAlmostEqual(by_road["west"], 4 / 3)
        self.assertAlmostEqual(sum(by_road.values()), self.m.average_queue_length)

    def test_travel_time_and_stops(self):
        self.assertAlmostEqual(self.m.average_travel_time, (40 + 50 + 30) / 3)
        self.assertAlmostEqual(self.m.average_stops, (1 + 2 + 0) / 3)
        self.assertEqual(self.m.total_stops, 1 + 2 + 0 + 3)

    def test_throughput_is_vehicles_served_per_minute(self):
        self.assertAlmostEqual(self.m.throughput_per_minute, 3 / 10)  # 3 vehicles in 10 minutes

    def test_identity_fields(self):
        self.assertEqual((self.m.controller, self.m.scenario, self.m.seed, self.m.duration),
                         ("test", "balanced", 42, 600.0))


class NothingHappenedTests(unittest.TestCase):
    def test_undefined_averages_are_none_and_never_zero(self):
        sim = Simulator(Settings())
        m = MetricsCollector().result(sim, "idle")
        for name in ("average_waiting_time", "average_waiting_time_all", "max_waiting_time",
                     "average_queue_length", "average_travel_time", "average_stops"):
            self.assertIsNone(getattr(m, name), name)
        self.assertEqual((m.vehicles_arrived, m.vehicles_served, m.max_queue_length, m.total_stops), (0, 0, 0, 0))
        self.assertEqual(m.average_queue_by_road, {})
        self.assertEqual(m.throughput_per_minute, 0.0)

    def test_no_served_vehicles_but_some_waiting(self):
        sim = Simulator(Settings())
        sim.time = 60.0
        sim.roads[N].backlog.append(vehicle(1, 30, 30, 1, completed=False))
        m = MetricsCollector().result(sim, "stuck")
        self.assertIsNone(m.average_waiting_time)
        self.assertEqual(m.average_waiting_time_all, 30)
        self.assertEqual(m.throughput_per_minute, 0.0)
        self.assertEqual(m.vehicles_unserved, 1)

    def test_formatting_shows_na_for_missing_values(self):
        text = "\n".join(format_metrics(MetricsCollector().result(Simulator(Settings()), "idle")))
        self.assertIn("n/a", text)
        self.assertNotIn("None", text)


class ExportTests(unittest.TestCase):
    def test_to_dict_is_json_serialisable_and_complete(self):
        sim, collector = hand_made_run()
        m = collector.result(sim, "test")
        data = json.loads(json.dumps(m.to_dict()))
        self.assertEqual({f.name for f in dataclasses.fields(EpisodeMetrics)}, set(data))
        self.assertEqual(data["vehicles_served"], 3)

    def test_formatted_table_contains_the_numbers(self):
        sim, collector = hand_made_run()
        text = "\n".join(format_metrics(collector.result(sim, "test")))
        for fragment in ("Vehicles served           : 3", "(0.3 per minute)", "10.0 s",
                         "22.5 s", "5.0 vehicles", "PASSED"):
            self.assertIn(fragment, text)

    def test_formatted_table_reports_a_failed_safety_check(self):
        sim, collector = hand_made_run()
        sim.safety_violations = 4
        self.assertIn("FAILED", "\n".join(format_metrics(collector.result(sim, "test"))))


class ImprovementTests(unittest.TestCase):
    def test_lower_is_better(self):
        # the example from the project brief: 42.7 s -> 28.4 s
        self.assertAlmostEqual(improvement_percent(42.7, 28.4), 33.49, places=2)

    def test_higher_is_better(self):
        self.assertAlmostEqual(improvement_percent(184, 221, lower_is_better=False), 20.11, places=2)

    def test_worse_results_are_negative(self):
        self.assertAlmostEqual(improvement_percent(10, 15), -50.0)
        self.assertAlmostEqual(improvement_percent(100, 80, lower_is_better=False), -20.0)

    def test_equal_values_give_zero_even_for_zero(self):
        self.assertEqual(improvement_percent(5.0, 5.0), 0.0)
        self.assertEqual(improvement_percent(0.0, 0.0), 0.0)

    def test_undefined_cases_give_none(self):
        self.assertIsNone(improvement_percent(0.0, 3.0))
        self.assertIsNone(improvement_percent(None, 3.0))
        self.assertIsNone(improvement_percent(3.0, None))

    def test_compare_metrics_uses_the_right_direction_for_every_metric(self):
        sim, collector = hand_made_run()
        base = collector.result(sim, "fixed")
        better = dataclasses.replace(
            base, controller="rl", average_waiting_time=base.average_waiting_time / 2,
            average_queue_length=base.average_queue_length / 2,
            vehicles_served=base.vehicles_served * 2,
            throughput_per_minute=base.throughput_per_minute * 2)
        changes = compare_metrics(base, better)
        self.assertEqual(set(changes), set(LOWER_IS_BETTER) | set(HIGHER_IS_BETTER))
        self.assertAlmostEqual(changes["average_waiting_time"], 50.0)
        self.assertAlmostEqual(changes["average_queue_length"], 50.0)
        self.assertAlmostEqual(changes["vehicles_served"], 100.0)
        self.assertAlmostEqual(changes["throughput_per_minute"], 100.0)
        self.assertAlmostEqual(changes["average_travel_time"], 0.0)

    def test_metric_names_all_exist_on_the_results(self):
        names = {f.name for f in dataclasses.fields(EpisodeMetrics)}
        self.assertTrue(set(LOWER_IS_BETTER + HIGHER_IS_BETTER) <= names)


class TimeSeriesTests(unittest.TestCase):
    def test_samples_are_taken_at_the_requested_interval(self):
        collector = MetricsCollector(sample_interval=5.0)
        for i in range(1, 25):  # 0.5 s ... 12.0 s
            collector.record_values(i * 0.5, queues(n=i), i)
        self.assertEqual(collector.series.times, [0.5, 5.0, 10.0])
        self.assertEqual(collector.series.total_queue, [1, 10, 20])
        self.assertEqual(collector.series.vehicles_in_system, [1, 10, 20])

    def test_average_wait_so_far_is_none_until_a_vehicle_is_served(self):
        collector = MetricsCollector(sample_interval=1.0)
        collector.record_values(1.0, queues(), 3, completed_count=0, completed_wait_sum=0.0)
        collector.record_values(2.0, queues(), 3, completed_count=2, completed_wait_sum=30.0)
        self.assertEqual(collector.series.average_wait_so_far, [None, 15.0])

    def test_reset_clears_everything(self):
        collector = MetricsCollector()
        collector.record_values(1.0, queues(n=5), 5)
        collector.reset()
        self.assertEqual((collector.steps, collector.series.times), (0, []))

    def test_invalid_sample_interval(self):
        for bad in (0, -1, float("nan")):
            with self.assertRaises(ValueError):
                MetricsCollector(sample_interval=bad)


if __name__ == "__main__":
    unittest.main()
