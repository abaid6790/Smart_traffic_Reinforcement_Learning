import json
import tempfile
import unittest
from pathlib import Path

from config.settings import (
    DIRECTION_NAMES,
    SCENARIO_NAMES,
    SCENARIOS,
    ConfigError,
    Settings,
    get_scenario,
)
from environment.enums import Direction


class DefaultsTests(unittest.TestCase):
    def test_defaults_are_valid(self):
        self.assertEqual(Settings().problems(), [])

    def test_direction_names_match_the_enum(self):
        self.assertEqual(DIRECTION_NAMES, tuple(d.value for d in Direction))

    def test_every_scenario_defines_every_road_with_sane_rates(self):
        for name, profile in SCENARIOS.items():
            self.assertEqual(profile.name, name)
            self.assertEqual(set(profile.rates), set(DIRECTION_NAMES))
            self.assertTrue(all(rate > 0 for rate in profile.rates.values()))

    def test_all_requested_scenarios_exist(self):
        wanted = {"low", "medium", "high", "rush_hour", "balanced", "uneven", "random"}
        self.assertEqual(set(SCENARIO_NAMES), wanted)

    def test_unknown_scenario_has_helpful_message(self):
        with self.assertRaises(ConfigError) as ctx:
            get_scenario("nope")
        self.assertIn("rush_hour", str(ctx.exception))


class ValidationTests(unittest.TestCase):
    def assert_rejected(self, section, **change):
        with self.assertRaises(ConfigError, msg=f"{section} {change}"):
            Settings().with_changes(section, **change)

    def test_rl_ranges_from_the_project_brief(self):
        self.assert_rejected("rl", learning_rate=0.0)
        self.assert_rejected("rl", learning_rate=1.5)
        self.assert_rejected("rl", discount_factor=-0.1)
        self.assert_rejected("rl", discount_factor=1.1)
        self.assert_rejected("rl", epsilon=-0.1)
        self.assert_rejected("rl", epsilon=1.1)
        self.assert_rejected("rl", episodes=0)
        self.assert_rejected("rl", episodes=-5)

    def test_rl_boundary_values_are_accepted(self):
        settings = Settings().with_changes("rl", learning_rate=1.0, discount_factor=0.0,
                                           epsilon=0.0, epsilon_min=0.0)
        self.assertEqual(settings.rl.learning_rate, 1.0)

    def test_epsilon_min_cannot_exceed_epsilon(self):
        self.assert_rejected("rl", epsilon=0.1, epsilon_min=0.5)

    def test_invalid_seeds_are_rejected(self):
        self.assert_rejected("traffic", seed=-1)
        self.assert_rejected("traffic", seed=2**32)

    def test_unknown_scenario_is_rejected(self):
        self.assert_rejected("traffic", scenario="gridlock")

    def test_light_timings(self):
        self.assert_rejected("lights", min_green=0)
        self.assert_rejected("lights", min_green=30, max_green=20)
        self.assert_rejected("lights", yellow=0)
        self.assert_rejected("lights", all_red=-1)
        self.assert_rejected("lights", initial_phase="XX")

    def test_yellow_plus_all_red_must_clear_the_intersection(self):
        self.assert_rejected("lights", yellow=0.5, all_red=0.0)

    def test_simulation_values(self):
        self.assert_rejected("simulation", dt=0)
        self.assert_rejected("simulation", dt=5)
        self.assert_rejected("simulation", duration=-1)
        self.assert_rejected("simulation", max_speed_kmh=0)
        self.assert_rejected("simulation", speed_variation=0.9)
        self.assert_rejected("simulation", dt=float("nan"))

    def test_display_values(self):
        self.assert_rejected("display", simulation_speed=3.0)
        self.assert_rejected("display", theme="neon")
        self.assert_rejected("display", fps=1)

    def test_direction_weights(self):
        self.assert_rejected("traffic", direction_weights={"up": 1.0})
        self.assert_rejected("traffic", direction_weights={"north": -1.0})
        self.assert_rejected("traffic", direction_weights={"north": 0.0})
        ok = Settings().with_changes("traffic", direction_weights={"north": 3.0, "south": 1.0})
        self.assertEqual(ok.traffic.direction_weights["north"], 3.0)

    def test_max_vehicles(self):
        self.assert_rejected("traffic", max_vehicles=0)
        self.assertEqual(Settings().with_changes("traffic", max_vehicles=10).traffic.max_vehicles, 10)

    def test_all_problems_are_reported_together(self):
        data = {"rl": {"learning_rate": 5.0, "episodes": 0}, "traffic": {"seed": -3}}
        # type-correct but out of range -> all three reported in one error
        with self.assertRaises(ConfigError) as ctx:
            Settings.from_dict(data)
        self.assertGreaterEqual(len(ctx.exception.problems), 3)

    def test_unknown_names_and_bad_values_are_reported_in_the_same_pass(self):
        data = {"rl": {"learning_rate": 3, "typo": 1}, "traffic": {"scenario": "gridlock"}}
        with self.assertRaises(ConfigError) as ctx:
            Settings.from_dict(data)
        text = str(ctx.exception)
        for fragment in ("rl.typo", "rl.learning_rate", "gridlock"):
            self.assertIn(fragment, text)

    def test_with_changes_rejects_unknown_names(self):
        with self.assertRaises(ConfigError):
            Settings().with_changes("traffic", sed=1)
        with self.assertRaises(ConfigError):
            Settings().with_changes("nonsense", seed=1)

    def test_with_changes_cannot_touch_methods_or_properties(self):
        for name in ("problems", "max_speed_ms"):
            with self.assertRaises(ConfigError, msg=name):
                Settings().with_changes("simulation", **{name: 1})

    def test_with_changes_checks_types_like_a_settings_file_does(self):
        with self.assertRaises(ConfigError):
            Settings().with_changes("rl", learning_rate="fast")
        with self.assertRaises(ConfigError):
            Settings().with_changes("traffic", seed=1.5)
        self.assertIsInstance(Settings().with_changes("simulation", duration=300).simulation.duration, float)

    def test_updated_changes_several_sections_at_once(self):
        new = Settings().updated(traffic={"seed": 3}, rl={"episodes": 50}, display={"theme": "light"})
        self.assertEqual((new.traffic.seed, new.rl.episodes, new.display.theme), (3, 50, "light"))

    def test_updated_validates_the_combination_not_each_part(self):
        # Valid only together: a shorter max green needs shorter fixed greens.
        with self.assertRaises(ConfigError):
            Settings().updated(lights={"max_green": 20})
        self.assertEqual(
            Settings().updated(lights={"max_green": 20}, fixed={"ns_green": 20, "ew_green": 20}).lights.max_green, 20.0)

    def test_updated_rejects_bad_section_names_and_shapes(self):
        with self.assertRaises(ConfigError):
            Settings().updated(nonsense={"a": 1})
        with self.assertRaises(ConfigError):
            Settings().updated(traffic=5)

    def test_updated_leaves_the_original_unchanged(self):
        original = Settings()
        original.updated(traffic={"seed": 123})
        self.assertEqual(original.traffic.seed, 42)

    def test_with_changes_does_not_modify_the_original(self):
        original = Settings()
        changed = original.with_changes("traffic", seed=99)
        self.assertEqual(original.traffic.seed, 42)
        self.assertEqual(changed.traffic.seed, 99)


class SerialisationTests(unittest.TestCase):
    def test_dict_round_trip(self):
        settings = Settings().with_changes("traffic", scenario="rush_hour", seed=7)
        self.assertEqual(Settings.from_dict(settings.to_dict()), settings)

    def test_partial_dict_uses_defaults(self):
        settings = Settings.from_dict({"traffic": {"seed": 5}})
        self.assertEqual(settings.traffic.seed, 5)
        self.assertEqual(settings.rl, Settings().rl)

    def test_ints_are_accepted_for_float_settings(self):
        settings = Settings.from_dict({"simulation": {"duration": 300}})
        self.assertEqual(settings.simulation.duration, 300.0)
        self.assertIsInstance(settings.simulation.duration, float)

    def test_unknown_names_are_rejected(self):
        with self.assertRaises(ConfigError) as ctx:
            Settings.from_dict({"traffic": {"sede": 1}})
        self.assertIn("traffic.sede", str(ctx.exception))
        with self.assertRaises(ConfigError):
            Settings.from_dict({"colour": {}})

    def test_wrong_types_are_rejected(self):
        for bad in (
            {"traffic": {"seed": "abc"}},
            {"traffic": {"seed": 1.5}},
            {"traffic": {"seed": True}},
            {"rl": {"learning_rate": "fast"}},
            {"rl": {"learning_rate": None}},
            {"display": {"show_debug": "yes"}},
            {"traffic": {"scenario": 3}},
            {"traffic": {"direction_weights": [1, 2]}},
            {"traffic": "oops"},
            ["not", "a", "dict"],
        ):
            with self.assertRaises(ConfigError, msg=str(bad)):
                Settings.from_dict(bad)

    def test_null_is_allowed_for_optional_values(self):
        settings = Settings.from_dict({"traffic": {"max_vehicles": None, "direction_weights": None}})
        self.assertIsNone(settings.traffic.max_vehicles)


class FileTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def test_save_then_load(self):
        path = self.dir / "nested" / "settings.json"
        settings = Settings().with_changes("traffic", scenario="uneven", seed=11)
        settings.save(path)
        self.assertEqual(Settings.load(path), settings)
        self.assertEqual([p.name for p in path.parent.iterdir()], ["settings.json"])

    def test_saved_file_is_readable_json(self):
        path = self.dir / "s.json"
        Settings().save(path)
        self.assertIn("traffic", json.loads(path.read_text(encoding="utf-8")))

    def test_invalid_settings_are_not_saved(self):
        path = self.dir / "s.json"
        bad = Settings()
        bad.rl.learning_rate = 7.0
        with self.assertRaises(ConfigError):
            bad.save(path)
        self.assertFalse(path.exists())

    def test_missing_file(self):
        with self.assertRaises(ConfigError) as ctx:
            Settings.load(self.dir / "missing.json")
        self.assertIn("not found", str(ctx.exception))

    def test_corrupted_file(self):
        path = self.dir / "bad.json"
        path.write_text("{ this is not json", encoding="utf-8")
        with self.assertRaises(ConfigError) as ctx:
            Settings.load(path)
        self.assertIn("not valid JSON", str(ctx.exception))

    def test_binary_garbage_file(self):
        path = self.dir / "garbage.json"
        path.write_bytes(b"\xff\xfe\x00\x81\x82")
        with self.assertRaises(ConfigError):
            Settings.load(path)

    def test_valid_json_with_invalid_values(self):
        path = self.dir / "values.json"
        path.write_text(json.dumps({"rl": {"learning_rate": 2}}), encoding="utf-8")
        with self.assertRaises(ConfigError) as ctx:
            Settings.load(path)
        self.assertIn("learning_rate", str(ctx.exception))

    def test_unwritable_location_gives_config_error(self):
        blocker = self.dir / "blocker"
        blocker.write_text("a file, not a folder", encoding="utf-8")
        with self.assertRaises(ConfigError):
            Settings().save(blocker / "settings.json")


if __name__ == "__main__":
    unittest.main()
