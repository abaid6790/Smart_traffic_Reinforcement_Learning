import random
import unittest

from config.settings import SCENARIO_NAMES, Settings
from environment.enums import ALL_DIRECTIONS, Direction, SignalColor
from environment.vehicle import Vehicle
from simulation.simulator import Simulator


def make_settings(scenario="medium", seed=1, duration=300.0, **lights):
    settings = Settings().with_changes("traffic", scenario=scenario, seed=seed)
    settings = settings.with_changes("simulation", duration=duration)
    if lights:
        # The fixed-time greens must stay inside the light's limits, so move them too.
        green = lights.get("min_green", settings.lights.min_green)
        settings = settings.updated(
            lights=lights, fixed={"ns_green": green, "ew_green": green}
        )
    return settings


def run_with_checks(settings, request_probability=0.0, control_seed=0, controller=None):
    """Run a full simulation, checking safety rules on every single step.

    The light is driven either by random switch requests (``request_probability``)
    or by a ``controller``.  Returns (simulator, number_of_red_light_violations,
    number_of_overlaps).
    """
    sim = Simulator(settings)
    cfg = settings.simulation
    rng = random.Random(control_seed)
    red_runs = overlaps = 0
    while not sim.finished:
        if controller is not None:
            controller.act(sim)
        if rng.random() < request_probability:
            sim.light.request_switch()
        before = {
            v.id: (v.position, sim.light.color(d))
            for d, road in sim.roads.items()
            for v in road.vehicles
        }
        stop_line = cfg.road_length
        sim.step()
        for d, road in sim.roads.items():
            for v in road.vehicles + [c for c in sim.completed if c.direction is d][-5:]:
                if v.id in before:
                    pos, color = before[v.id]
                    if pos <= stop_line < v.position and color is SignalColor.RED:
                        red_runs += 1
            for leader, follower in zip(road.vehicles, road.vehicles[1:]):
                if leader.rear - follower.position < cfg.min_gap - 1e-6:
                    overlaps += 1
    return sim, red_runs, overlaps


class BasicTests(unittest.TestCase):
    def test_starts_empty_at_time_zero(self):
        sim = Simulator(make_settings())
        self.assertEqual((sim.time, sim.spawned, sim.vehicles_in_system(), len(sim.completed)), (0.0, 0, 0, 0))
        self.assertFalse(sim.finished)

    def test_step_advances_time_by_dt(self):
        sim = Simulator(make_settings())
        sim.step()
        sim.step()
        self.assertAlmostEqual(sim.time, 2 * sim.dt)
        self.assertEqual(sim.step_count, 2)

    def test_finishes_after_the_configured_duration(self):
        sim = Simulator(make_settings(duration=60))
        sim.run()
        self.assertTrue(sim.finished)
        self.assertAlmostEqual(sim.time, 60.0)

    def test_run_for_a_number_of_seconds(self):
        sim = Simulator(make_settings(duration=300))
        sim.run(10)
        self.assertAlmostEqual(sim.time, 10.0)
        self.assertFalse(sim.finished)

    def test_invalid_settings_are_rejected(self):
        bad = Settings()
        bad.rl.learning_rate = 9
        with self.assertRaises(ValueError):
            Simulator(bad)

    def test_reset_returns_to_the_start_and_replays_the_same_traffic(self):
        sim = Simulator(make_settings(duration=120))
        sim.run()
        first = sim.summary()
        sim.reset()
        self.assertEqual((sim.time, sim.spawned, len(sim.completed)), (0.0, 0, 0))
        sim.run()
        self.assertEqual(sim.summary(), first)

    def test_reset_with_a_different_seed_changes_the_traffic(self):
        sim = Simulator(make_settings(duration=300))
        sim.run()
        first = sim.spawned
        sim.reset(seed=999)
        sim.run()
        self.assertNotEqual(sim.spawned, first)

    def test_summary_has_expected_keys(self):
        sim = Simulator(make_settings())
        self.assertEqual(
            set(sim.summary()),
            {"time", "light", "queues", "spawned", "completed", "in_system", "switches", "safety_violations"},
        )

    def test_phase_queue_adds_the_right_roads(self):
        sim = Simulator(make_settings())
        for road, count in ((Direction.NORTH, 2), (Direction.SOUTH, 3), (Direction.EAST, 4)):
            for i in range(count):
                sim.roads[road].add_arrival(Vehicle(id=100 + i, direction=road, max_speed=10.0, length=4.5))
        from environment.enums import Phase
        self.assertEqual(sim.phase_queue(Phase.NS), 5)
        self.assertEqual(sim.phase_queue(Phase.EW), 4)


class ConflictDetectorTests(unittest.TestCase):
    """The safety check must really be able to fail, or passing means nothing."""

    def put_in_box(self, sim, direction, vid):
        road = sim.roads[direction]
        vehicle = Vehicle(id=vid, direction=direction, max_speed=10.0, length=4.5,
                          position=road.stop_line + 5.0, entered=True)
        road.vehicles.append(vehicle)

    def test_detects_vehicles_from_both_road_pairs_in_the_box(self):
        sim = Simulator(make_settings())
        self.put_in_box(sim, Direction.NORTH, 1)
        self.put_in_box(sim, Direction.EAST, 2)
        self.assertTrue(sim._crossing_conflict())

    def test_does_not_flag_vehicles_from_the_same_road_pair(self):
        sim = Simulator(make_settings())
        self.put_in_box(sim, Direction.NORTH, 1)
        self.put_in_box(sim, Direction.SOUTH, 2)
        self.assertFalse(sim._crossing_conflict())

    def test_step_counts_a_violation_when_a_conflict_exists(self):
        sim = Simulator(make_settings())
        self.put_in_box(sim, Direction.NORTH, 1)
        self.put_in_box(sim, Direction.WEST, 2)
        sim.step()
        self.assertGreaterEqual(sim.safety_violations, 1)


class SafetyInvariantTests(unittest.TestCase):
    def test_every_scenario_is_safe_with_the_default_light_cycle(self):
        for name in SCENARIO_NAMES:
            sim, red_runs, overlaps = run_with_checks(make_settings(name, seed=3, duration=400))
            self.assertEqual(sim.safety_violations, 0, f"{name}: crossing conflict")
            self.assertEqual(red_runs, 0, f"{name}: red light run")
            self.assertEqual(overlaps, 0, f"{name}: vehicles overlapped")

    def test_safe_even_when_a_controller_requests_switches_constantly(self):
        for p in (0.05, 0.5, 1.0):
            sim, red_runs, overlaps = run_with_checks(
                make_settings("rush_hour", seed=8, duration=400), request_probability=p)
            self.assertEqual((sim.safety_violations, red_runs, overlaps), (0, 0, 0), f"p={p}")
            self.assertGreater(sim.light.switch_count, 3)

    def test_safe_with_short_timings_and_a_coarse_time_step(self):
        settings = (make_settings("high", seed=2, duration=300, min_green=5, max_green=15, yellow=4, all_red=2)
                    .with_changes("simulation", dt=1.0))
        sim, red_runs, overlaps = run_with_checks(settings, request_probability=0.5)
        self.assertEqual((sim.safety_violations, red_runs, overlaps), (0, 0, 0))

    def test_safe_with_a_fine_time_step(self):
        settings = make_settings("high", seed=2, duration=200).with_changes("simulation", dt=0.1)
        sim, red_runs, overlaps = run_with_checks(settings, request_probability=0.01)
        self.assertEqual((sim.safety_violations, red_runs, overlaps), (0, 0, 0))

    def test_speeds_stay_within_limits_and_positions_never_go_backwards(self):
        settings = make_settings("rush_hour", seed=5, duration=300)
        sim = Simulator(settings)
        limit = settings.simulation.max_speed_ms * (1 + settings.simulation.speed_variation)
        last_position = {}
        while not sim.finished:
            sim.step()
            for road in sim.roads.values():
                for v in road.vehicles:
                    self.assertGreaterEqual(v.speed, 0.0)
                    self.assertLessEqual(v.speed, limit + 1e-6)
                    self.assertGreaterEqual(v.position, last_position.get(v.id, 0.0))
                    last_position[v.id] = v.position


class FlowTests(unittest.TestCase):
    def test_vehicles_are_conserved(self):
        for name in ("low", "rush_hour", "uneven"):
            sim = Simulator(make_settings(name, seed=4, duration=400))
            sim.run()
            self.assertEqual(sim.spawned, len(sim.completed) + sim.vehicles_in_system(), name)
            self.assertEqual(len(sim.all_vehicles()), sim.spawned)

    def test_every_vehicle_eventually_leaves_when_traffic_stops(self):
        settings = make_settings("medium", seed=6, duration=1500).with_changes("traffic", max_vehicles=40)
        sim = Simulator(settings)
        sim.run()
        self.assertEqual(sim.spawned, 40)
        self.assertEqual(sim.vehicles_in_system(), 0, "a vehicle got permanently stuck")
        self.assertEqual(len(sim.completed), 40)

    def test_every_road_gets_served_in_heavy_traffic(self):
        sim = Simulator(make_settings("rush_hour", seed=1, duration=600))
        sim.run()
        for d in ALL_DIRECTIONS:
            served = sum(1 for v in sim.completed if v.direction is d)
            self.assertGreater(served, 10, d.value)

    def test_completed_vehicles_have_sensible_statistics(self):
        sim = Simulator(make_settings("high", seed=2, duration=400))
        sim.run()
        self.assertGreater(len(sim.completed), 20)
        free_flow = (sim.settings.simulation.road_length + sim.settings.simulation.intersection_length
                     + sim.settings.simulation.exit_length) / (sim.settings.simulation.max_speed_ms * 1.15)
        for v in sim.completed:
            self.assertTrue(v.completed)
            self.assertGreaterEqual(v.waiting_time, 0.0)
            self.assertLessEqual(v.waiting_time, v.travel_time + 1e-6)
            self.assertGreaterEqual(v.travel_time, free_flow * 0.95)
            self.assertGreaterEqual(v.stops, 0)

    def test_red_light_actually_creates_a_queue_and_green_clears_it(self):
        settings = make_settings("balanced", seed=1, duration=600, min_green=10, max_green=60)
        sim = Simulator(settings)
        peak_ew = 0
        # NS is green first, so EW builds up a queue.
        while sim.time < 55:
            sim.step()
            peak_ew = max(peak_ew, sim.phase_queue(sim.light.phase.other))
        self.assertGreaterEqual(peak_ew, 2)
        sim.run(60)  # long enough for EW to get a green and clear
        self.assertLess(sim.phase_queue(sim.light.phase.other) + sim.phase_queue(sim.light.phase), peak_ew + 12)


class DeterminismAndFairnessTests(unittest.TestCase):
    def test_identical_runs_give_identical_results(self):
        results = []
        for _ in range(2):
            sim = Simulator(make_settings("random", seed=21, duration=400))
            sim.run()
            results.append((sim.summary(), [(v.id, v.waiting_time, v.travel_time, v.stops) for v in sim.completed]))
        self.assertEqual(results[0], results[1])

    def test_traffic_is_identical_whatever_the_light_does(self):
        """Fair comparison: the controller must not change which vehicles arrive."""
        settings = make_settings("uneven", seed=33, duration=400)
        passive, _, _ = run_with_checks(settings, request_probability=0.0)
        active, _, _ = run_with_checks(settings, request_probability=0.3, control_seed=5)
        self.assertNotEqual(passive.light.switch_count, active.light.switch_count)

        def arrivals(sim):
            return [(v.id, v.direction, v.spawn_time, round(v.max_speed, 9)) for v in sim.all_vehicles()]

        self.assertEqual(arrivals(passive), arrivals(active))


if __name__ == "__main__":
    unittest.main()
