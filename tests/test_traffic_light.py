import random
import unittest

from config.settings import TrafficLightConfig
from environment.enums import ALL_DIRECTIONS, Direction, LightStage, Phase, SignalColor
from environment.traffic_light import TrafficLight

DT = 0.5


def make_light(**kwargs):
    return TrafficLight(TrafficLightConfig(**kwargs))


def run(light, seconds):
    for _ in range(int(round(seconds / DT))):
        light.update(DT)


class InitialStateTests(unittest.TestCase):
    def test_starts_with_north_south_green(self):
        light = make_light()
        self.assertEqual((light.phase, light.stage), (Phase.NS, LightStage.GREEN))
        self.assertEqual(light.color(Direction.NORTH), SignalColor.GREEN)
        self.assertEqual(light.color(Direction.SOUTH), SignalColor.GREEN)
        self.assertEqual(light.color(Direction.EAST), SignalColor.RED)
        self.assertEqual(light.color(Direction.WEST), SignalColor.RED)

    def test_initial_phase_can_be_east_west(self):
        light = make_light(initial_phase="EW")
        self.assertEqual(light.color(Direction.EAST), SignalColor.GREEN)
        self.assertEqual(light.color(Direction.NORTH), SignalColor.RED)


class SwitchingTests(unittest.TestCase):
    def test_request_is_refused_before_min_green(self):
        light = make_light(min_green=10, max_green=60)
        run(light, 9.5)
        self.assertFalse(light.can_switch())
        self.assertFalse(light.request_switch())
        self.assertEqual(light.stage, LightStage.GREEN)
        self.assertEqual(light.switch_count, 0)

    def test_request_is_accepted_after_min_green_and_goes_yellow(self):
        light = make_light(min_green=10, max_green=60)
        run(light, 10)
        self.assertTrue(light.can_switch())
        self.assertTrue(light.request_switch())
        self.assertEqual(light.stage, LightStage.YELLOW)
        self.assertEqual(light.color(Direction.NORTH), SignalColor.YELLOW)
        self.assertEqual(light.color(Direction.EAST), SignalColor.RED)
        self.assertEqual(light.switch_count, 1)

    def test_requests_during_yellow_and_all_red_are_ignored(self):
        light = make_light(min_green=1, yellow=5, all_red=2)
        run(light, 1)
        light.request_switch()
        self.assertFalse(light.request_switch())
        run(light, 5)
        self.assertEqual(light.stage, LightStage.ALL_RED)
        self.assertFalse(light.request_switch())

    def test_full_sequence_timing_is_exact(self):
        light = make_light(min_green=5, max_green=60, yellow=5, all_red=2)
        run(light, 5)
        light.request_switch()
        run(light, 4.5)
        self.assertEqual(light.stage, LightStage.YELLOW)
        run(light, 0.5)
        self.assertEqual(light.stage, LightStage.ALL_RED)
        run(light, 1.5)
        self.assertEqual(light.stage, LightStage.ALL_RED)
        self.assertTrue(all(light.color(d) is SignalColor.RED for d in ALL_DIRECTIONS))
        run(light, 0.5)
        self.assertEqual((light.phase, light.stage), (Phase.EW, LightStage.GREEN))
        self.assertEqual(light.color(Direction.EAST), SignalColor.GREEN)
        self.assertEqual(light.color(Direction.NORTH), SignalColor.RED)

    def test_light_switches_by_itself_at_max_green(self):
        light = make_light(min_green=5, max_green=20, yellow=5, all_red=2)
        run(light, 19.5)
        self.assertEqual(light.stage, LightStage.GREEN)
        run(light, 0.5)
        self.assertEqual(light.stage, LightStage.YELLOW)
        self.assertEqual(light.switch_count, 1)

    def test_phases_alternate(self):
        light = make_light(min_green=1, max_green=4, yellow=2, all_red=1)
        seen = []
        for _ in range(60):
            light.update(DT)
            if light.stage is LightStage.GREEN and (not seen or seen[-1] != light.phase):
                seen.append(light.phase)
        self.assertEqual(seen[:4], [Phase.NS, Phase.EW, Phase.NS, Phase.EW])

    def test_time_left_in_stage(self):
        light = make_light(max_green=20)
        run(light, 5)
        self.assertAlmostEqual(light.time_left_in_stage(), 15.0)

    def test_leftover_time_carries_into_the_next_stage(self):
        light = make_light(min_green=1, max_green=10, yellow=5, all_red=2)
        light.update(10.3)  # one big step overshoots the end of green by 0.3 s
        self.assertEqual(light.stage, LightStage.YELLOW)
        self.assertAlmostEqual(light.stage_time, 0.3)

    def test_reset_restores_initial_state(self):
        light = make_light(min_green=1)
        run(light, 30)
        light.reset()
        self.assertEqual((light.phase, light.stage, light.stage_time, light.switch_count),
                         (Phase.NS, LightStage.GREEN, 0.0, 0))

    def test_describe_is_readable(self):
        self.assertEqual(make_light().describe(), "NS GREEN 0.0s")


class SafetyTests(unittest.TestCase):
    def test_conflicting_greens_are_impossible_under_random_requests(self):
        rng = random.Random(1234)
        light = make_light(min_green=3, max_green=15, yellow=3, all_red=1)
        for _ in range(20_000):
            if rng.random() < 0.4:
                light.request_switch()
            light.update(DT)
            self.assertTrue(light.is_conflict_free())
            greens = {d.phase for d in ALL_DIRECTIONS if light.color(d) is SignalColor.GREEN}
            self.assertLessEqual(len(greens), 1)

    def test_green_never_ends_before_min_green_even_with_constant_requests(self):
        light = make_light(min_green=8, max_green=30, yellow=3, all_red=1)
        green_start = 0.0
        clock = 0.0
        was_green = True
        for _ in range(10_000):
            light.request_switch()
            light.update(DT)
            clock += DT
            now_green = light.stage is LightStage.GREEN
            if was_green and not now_green:
                self.assertGreaterEqual(clock - green_start, 8.0 - 1e-6)
            if now_green and not was_green:
                green_start = clock
            was_green = now_green

    def test_green_never_lasts_longer_than_max_green(self):
        rng = random.Random(5)
        light = make_light(min_green=5, max_green=25, yellow=3, all_red=1)
        green_for = 0.0
        for _ in range(20_000):
            if rng.random() < 0.05:
                light.request_switch()
            light.update(DT)
            green_for = green_for + DT if light.stage is LightStage.GREEN else 0.0
            self.assertLessEqual(green_for, 25.0 + 1e-6)

    def test_every_change_of_phase_goes_through_yellow_then_all_red(self):
        rng = random.Random(9)
        light = make_light(min_green=2, max_green=10, yellow=3, all_red=1)
        stages = []
        for _ in range(5_000):
            if rng.random() < 0.3:
                light.request_switch()
            light.update(DT)
            if not stages or stages[-1] != (light.stage, light.phase):
                stages.append((light.stage, light.phase))
        for (s1, p1), (s2, p2) in zip(stages, stages[1:]):
            if s1 is LightStage.GREEN:
                self.assertEqual((s2, p2), (LightStage.YELLOW, p1))
            elif s1 is LightStage.YELLOW:
                self.assertEqual((s2, p2), (LightStage.ALL_RED, p1))
            else:
                self.assertEqual((s2, p2), (LightStage.GREEN, p1.other))


if __name__ == "__main__":
    unittest.main()
