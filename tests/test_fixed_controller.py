import unittest

from config.settings import SCENARIO_NAMES, ConfigError, Settings
from controllers.base import Controller
from controllers.fixed_controller import FixedTimeController
from environment.enums import LightStage, Phase
from simulation.simulator import Simulator
from tests.test_simulator import run_with_checks


def make_settings(scenario="medium", seed=1, duration=600.0, **fixed):
    settings = Settings().with_changes("traffic", scenario=scenario, seed=seed)
    settings = settings.with_changes("simulation", duration=duration)
    return settings.with_changes("fixed", **fixed) if fixed else settings


def observed_stages(settings, seconds):
    """What the drivers see: a list of (phase, stage, seconds) for complete stages.

    The state is sampled just before each step, after the controller has acted,
    because that is the signal the vehicles obey during the step.
    """
    sim = Simulator(settings)
    controller = FixedTimeController(settings)
    runs = []
    current, length = (sim.light.phase, sim.light.stage), 0.0
    while sim.time < seconds:
        controller.act(sim)
        key = (sim.light.phase, sim.light.stage)
        if key == current:
            length += sim.dt
        else:
            runs.append((*current, length))
            current, length = key, sim.dt
        sim.step()
    return runs  # the last, unfinished stage is not included


class InterfaceTests(unittest.TestCase):
    def test_is_a_controller_with_a_name_and_description(self):
        controller = FixedTimeController(Settings())
        self.assertIsInstance(controller, Controller)
        self.assertEqual(controller.name, "fixed")
        self.assertIn("NS green 30 s", controller.describe())
        self.assertIn("cycle 74 s", controller.describe())

    def test_cycle_time(self):
        self.assertEqual(FixedTimeController(Settings()).cycle_time, 74.0)
        settings = make_settings(ns_green=20, ew_green=40)
        self.assertEqual(FixedTimeController(settings).cycle_time, 74.0)
        settings = settings.with_changes("lights", yellow=4.0, all_red=3.0)
        self.assertEqual(FixedTimeController(settings).cycle_time, 74.0)

    def test_invalid_settings_are_refused(self):
        bad = Settings()
        bad.fixed.ns_green = -3.0
        with self.assertRaises(ConfigError):
            FixedTimeController(bad)


class TimingTests(unittest.TestCase):
    def assert_cycle(self, runs, expected):
        self.assertGreaterEqual(len(runs), len(expected) * 2)
        for index, (phase, stage, seconds) in enumerate(runs[: len(expected) * 2]):
            want_phase, want_stage, want_seconds = expected[index % len(expected)]
            self.assertEqual((phase, stage), (want_phase, want_stage), f"stage {index}")
            self.assertAlmostEqual(seconds, want_seconds, delta=1e-6, msg=f"stage {index}")

    def test_default_cycle_matches_the_project_brief(self):
        # NS green 30, yellow 5, (all-red 2), EW green 30, yellow 5, (all-red 2)
        runs = observed_stages(make_settings(), 400)
        self.assert_cycle(runs, [
            (Phase.NS, LightStage.GREEN, 30), (Phase.NS, LightStage.YELLOW, 5),
            (Phase.NS, LightStage.ALL_RED, 2), (Phase.EW, LightStage.GREEN, 30),
            (Phase.EW, LightStage.YELLOW, 5), (Phase.EW, LightStage.ALL_RED, 2),
        ])

    def test_different_green_times_for_each_phase(self):
        runs = observed_stages(make_settings(ns_green=20, ew_green=45), 500)
        self.assert_cycle(runs, [
            (Phase.NS, LightStage.GREEN, 20), (Phase.NS, LightStage.YELLOW, 5),
            (Phase.NS, LightStage.ALL_RED, 2), (Phase.EW, LightStage.GREEN, 45),
            (Phase.EW, LightStage.YELLOW, 5), (Phase.EW, LightStage.ALL_RED, 2),
        ])

    def test_yellow_and_all_red_come_from_the_light_settings(self):
        settings = make_settings().with_changes("lights", yellow=4.0, all_red=3.0)
        runs = observed_stages(settings, 400)
        self.assertEqual([r[2] for r in runs[:3]], [30.0, 4.0, 3.0])

    def test_green_at_the_light_limits_is_accepted(self):
        for green in (10.0, 60.0):  # min_green and max_green
            runs = observed_stages(make_settings(ns_green=green, ew_green=green), 300)
            self.assertAlmostEqual(runs[0][2], green, delta=1e-6)

    def test_timing_is_exact_for_other_time_steps(self):
        for dt in (0.1, 0.25, 1.0):
            settings = make_settings(ns_green=20, ew_green=35).with_changes("simulation", dt=dt)
            runs = observed_stages(settings, 260)
            greens = [(p, s) for p, st, s in runs if st is LightStage.GREEN]
            self.assertAlmostEqual(greens[0][1], 20.0, delta=1e-6, msg=f"dt={dt}")
            self.assertAlmostEqual(greens[1][1], 35.0, delta=1e-6, msg=f"dt={dt}")
            self.assertAlmostEqual(greens[2][1], 20.0, delta=1e-6, msg=f"dt={dt}")

    def test_the_cycle_does_not_depend_on_traffic(self):
        def greens(scenario):
            runs = observed_stages(make_settings(scenario, ns_green=25, ew_green=15), 400)
            return [(p, s) for p, st, s in runs if st is LightStage.GREEN]

        self.assertEqual(greens("low"), greens("rush_hour"))
        self.assertEqual(greens("low"), greens("uneven"))

    def test_reset_has_no_effect_on_a_stateless_controller(self):
        controller = FixedTimeController(Settings())
        controller.reset()
        sim = Simulator(Settings())
        for _ in range(61):
            controller.act(sim)
            sim.step()
        self.assertEqual(sim.light.switch_count, 1)


class FixedConfigTests(unittest.TestCase):
    def test_defaults_match_the_project_brief(self):
        settings = Settings()
        self.assertEqual((settings.fixed.ns_green, settings.fixed.ew_green), (30.0, 30.0))
        self.assertEqual(settings.lights.yellow, 5.0)

    def test_green_times_must_be_positive_numbers(self):
        for bad in (0, -5, float("nan"), "long"):
            with self.assertRaises(ConfigError, msg=str(bad)):
                Settings().with_changes("fixed", ns_green=bad)

    def test_green_outside_the_light_limits_is_rejected_with_a_helpful_message(self):
        for change in ({"ns_green": 5}, {"ew_green": 90}):
            with self.assertRaises(ConfigError) as ctx:
                Settings().with_changes("fixed", **change)
            self.assertIn("lights.min_green", str(ctx.exception))
            self.assertIn("lights.max_green", str(ctx.exception))

    def test_changing_the_light_limits_alone_cannot_leave_the_baseline_invalid(self):
        with self.assertRaises(ConfigError):
            Settings().with_changes("lights", max_green=20)
        ok = Settings().updated(lights={"max_green": 20}, fixed={"ns_green": 15, "ew_green": 15})
        self.assertEqual(ok.fixed.ns_green, 15.0)

    def test_fixed_section_round_trips_through_json_dict(self):
        settings = Settings().with_changes("fixed", ns_green=22, ew_green=44)
        self.assertEqual(Settings.from_dict(settings.to_dict()), settings)
        self.assertEqual(settings.to_dict()["fixed"], {"ns_green": 22.0, "ew_green": 44.0})


class SafetyWithFixedControllerTests(unittest.TestCase):
    def test_every_scenario_is_safe(self):
        for name in SCENARIO_NAMES:
            settings = make_settings(name, seed=7, duration=600)
            sim, red_runs, overlaps = run_with_checks(
                settings, controller=FixedTimeController(settings))
            self.assertEqual((sim.safety_violations, red_runs, overlaps), (0, 0, 0), name)
            self.assertGreater(sim.light.switch_count, 10, name)

    def test_the_minimum_green_is_never_violated_even_with_short_greens(self):
        settings = Settings().updated(
            lights={"min_green": 5, "max_green": 20},
            fixed={"ns_green": 5, "ew_green": 5})
        settings = settings.with_changes("traffic", scenario="rush_hour")
        settings = settings.with_changes("simulation", duration=400)
        sim, red_runs, overlaps = run_with_checks(settings, controller=FixedTimeController(settings))
        self.assertEqual((sim.safety_violations, red_runs, overlaps), (0, 0, 0))

    def test_traffic_is_served_on_every_road(self):
        settings = make_settings("balanced", seed=5)
        sim, _, _ = run_with_checks(settings, controller=FixedTimeController(settings))
        from environment.enums import ALL_DIRECTIONS
        for direction in ALL_DIRECTIONS:
            self.assertGreater(sum(1 for v in sim.completed if v.direction is direction), 15)


if __name__ == "__main__":
    unittest.main()
