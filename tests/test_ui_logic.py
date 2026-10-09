"""Tests for the parts of the window that need no pygame."""

import random
import unittest

from config.settings import MAX_SEED, SPEED_CHOICES, ConfigError, Settings
from controllers.base import Controller
from controllers.fixed_controller import FixedTimeController
from environment.enums import ALL_DIRECTIONS, Direction, LightStage, Phase, SignalColor
from simulation.runner import run_episode
from simulation.simulator import Simulator
from ui.geometry import (
    LANE_WIDTH,
    VEHICLE_WIDTH,
    RoadLayout,
    ViewTransform,
    fit_view,
    heading,
    lane_side,
    right_of,
)
from ui.session import MAX_FRAME_SECONDS, SimulationSession
from ui.snapshot import Snapshot, VehicleView, capture, interpolate
from ui.theme import DARK, LIGHT, blend, get_theme

N, S, E, W = Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST


def make_settings(duration=120.0, scenario="high", seed=4, **display):
    settings = Settings().with_changes("simulation", duration=duration)
    settings = settings.with_changes("traffic", scenario=scenario, seed=seed)
    return settings.with_changes("display", **display) if display else settings


def layout(drive_on="right"):
    return RoadLayout.from_settings(make_settings(drive_on=drive_on))


def bounds(points):
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def overlap(a, b):
    ax0, ay0, ax1, ay1 = bounds(a)
    bx0, by0, bx1, by1 = bounds(b)
    return ax0 < bx1 - 1e-9 and bx0 < ax1 - 1e-9 and ay0 < by1 - 1e-9 and by0 < ay1 - 1e-9


class DisplaySettingsTests(unittest.TestCase):
    def test_defaults(self):
        display = Settings().display
        self.assertEqual((display.drive_on, display.view_range), ("right", 60.0))

    def test_invalid_values_are_rejected(self):
        for change in ({"drive_on": "up"}, {"view_range": 5}, {"view_range": 5000}, {"view_range": "far"}):
            with self.assertRaises(ConfigError, msg=str(change)):
                Settings().with_changes("display", **change)

    def test_left_hand_traffic_is_accepted(self):
        self.assertEqual(Settings().with_changes("display", drive_on="left").display.drive_on, "left")


class ThemeTests(unittest.TestCase):
    def test_both_themes_exist_and_differ(self):
        self.assertIs(get_theme("dark"), DARK)
        self.assertIs(get_theme("light"), LIGHT)
        self.assertNotEqual(DARK.background, LIGHT.background)

    def test_unknown_theme(self):
        with self.assertRaises(ConfigError):
            get_theme("neon")

    def test_every_colour_is_a_valid_rgb_triple(self):
        for theme in (DARK, LIGHT):
            for name, value in vars(theme).items():
                if name == "name":
                    continue
                self.assertEqual(len(value), 3, name)
                self.assertTrue(all(0 <= c <= 255 and isinstance(c, int) for c in value), name)

    def test_signal_colours_are_distinct(self):
        for theme in (DARK, LIGHT):
            self.assertEqual(len({theme.red, theme.yellow, theme.green, theme.lamp_off}), 4)

    def test_blend(self):
        self.assertEqual(blend((0, 0, 0), (100, 200, 50), 0), (0, 0, 0))
        self.assertEqual(blend((0, 0, 0), (100, 200, 50), 1), (100, 200, 50))
        self.assertEqual(blend((0, 0, 0), (100, 200, 50), 0.5), (50, 100, 25))
        self.assertEqual(blend((0, 0, 0), (100, 200, 50), 7), (100, 200, 50))


class GeometryTests(unittest.TestCase):
    def test_headings_are_unit_vectors_and_opposites_oppose(self):
        for d in ALL_DIRECTIONS:
            hx, hy = heading(d)
            self.assertAlmostEqual(hx * hx + hy * hy, 1.0)
        self.assertEqual(heading(N), (0.0, 1.0))
        self.assertEqual(tuple(-v for v in heading(N)), heading(S))
        self.assertEqual(tuple(-v for v in heading(E)), heading(W))

    def test_right_of_points_to_the_drivers_right(self):
        self.assertEqual(right_of(heading(N)), (-1.0, 0.0))  # heading south -> right is west
        self.assertEqual(right_of(heading(S)), (1.0, 0.0))  # heading north -> right is east
        self.assertEqual(right_of(heading(E)), (0.0, -1.0))  # heading west -> right is north
        self.assertEqual(right_of(heading(W)), (0.0, 1.0))  # heading east -> right is south

    def test_lane_side(self):
        self.assertEqual((lane_side("right"), lane_side("left")), (1.0, -1.0))

    def test_vehicles_arrive_from_the_correct_side_of_the_screen(self):
        L = layout()
        self.assertLess(L.lane_centre(N, -30)[1], 0)  # from the top
        self.assertGreater(L.lane_centre(S, -30)[1], 0)  # from the bottom
        self.assertGreater(L.lane_centre(E, -30)[0], 0)  # from the right
        self.assertLess(L.lane_centre(W, -30)[0], 0)  # from the left

    def test_right_hand_traffic_lanes(self):
        L = layout("right")
        self.assertEqual(L.lane_centre(N, -20), (-LANE_WIDTH / 2, -20))
        self.assertEqual(L.lane_centre(S, -20), (LANE_WIDTH / 2, 20))
        self.assertEqual(L.lane_centre(E, -20), (20, -LANE_WIDTH / 2))
        self.assertEqual(L.lane_centre(W, -20), (-20, LANE_WIDTH / 2))

    def test_left_hand_traffic_mirrors_the_lanes(self):
        right, left = layout("right"), layout("left")
        for d in ALL_DIRECTIONS:
            rx, ry = right.lane_centre(d, -20)
            lx, ly = left.lane_centre(d, -20)
            along_x = heading(d)[0] != 0
            self.assertEqual((lx, ly), (rx, -ry) if along_x else (-rx, ry))

    def test_opposite_directions_use_different_lanes(self):
        for drive_on in ("right", "left"):
            L = layout(drive_on)
            self.assertNotEqual(L.lane_centre(N, 0)[0], L.lane_centre(S, 0)[0])
            self.assertNotEqual(L.lane_centre(E, 0)[1], L.lane_centre(W, 0)[1])

    def test_distance_from_the_centre(self):
        L = layout()
        self.assertEqual(L.d_of(L.road_length), -L.box_half)  # stop line
        self.assertEqual(L.d_of(L.road_length + L.intersection_length), L.box_half)
        self.assertEqual(L.d_of(L.road_length + L.box_half), 0.0)

    def test_vehicle_corners_have_the_right_size_and_place(self):
        for drive_on in ("right", "left"):
            L = layout(drive_on)
            for d in ALL_DIRECTIONS:
                corners = L.vehicle_corners(d, position=L.road_length, length=4.5)  # front at stop line
                x0, y0, x1, y1 = bounds(corners)
                along_x = heading(d)[0] != 0
                length_extent, width_extent = (x1 - x0, y1 - y0) if along_x else (y1 - y0, x1 - x0)
                self.assertAlmostEqual(length_extent, 4.5)
                self.assertAlmostEqual(width_extent, VEHICLE_WIDTH)
                # in front of the stop line there must be nothing of the vehicle
                self.assertLessEqual(max(math_dot(c, heading(d)) for c in corners), -L.box_half + 1e-9)

    def test_vehicles_stay_inside_their_lane(self):
        L = layout()
        for d in ALL_DIRECTIONS:
            for corner in L.vehicle_corners(d, 100.0, 4.5):
                lateral = abs(corner[1] if heading(d)[0] else corner[0])
                self.assertGreater(lateral, 0.0)
                self.assertLess(lateral, L.road_half_width)

    def test_vehicles_in_opposite_lanes_never_overlap(self):
        L = layout()
        for position in (10.0, 100.0, L.road_length, L.road_length + 5):
            self.assertFalse(overlap(L.vehicle_corners(N, position, 4.5), L.vehicle_corners(S, position, 4.5)))
            self.assertFalse(overlap(L.vehicle_corners(E, position, 4.5), L.vehicle_corners(W, position, 4.5)))

    def test_vehicles_of_one_road_that_the_simulator_keeps_apart_do_not_overlap_on_screen(self):
        settings = make_settings(duration=300, scenario="rush_hour", seed=2)
        sim, controller, L = Simulator(settings), FixedTimeController(settings), layout()
        while not sim.finished:
            controller.act(sim)
            sim.step()
            for direction, road in sim.roads.items():
                shapes = [L.vehicle_corners(direction, v.position, v.length) for v in road.vehicles]
                for a, b in zip(shapes, shapes[1:]):
                    self.assertFalse(overlap(a, b), f"t={sim.time} {direction}")

    def test_fit_view(self):
        view = fit_view(1000, 600, half_extent=100)
        self.assertEqual(view.scale, 3.0)  # limited by the shorter side
        self.assertEqual(view.to_px((0, 0)), (500, 300))
        self.assertEqual(view.to_px((10, -10)), (530, 270))
        self.assertEqual(view.length_px(2), 6.0)
        self.assertAlmostEqual(view.visible_distance(N), 100.0)  # vertical roads: height limits
        self.assertAlmostEqual(view.visible_distance(E), 500 / 3.0)  # horizontal roads see further

    def test_fit_view_rejects_nonsense(self):
        for args in ((0, 100, 10), (100, 0, 10), (100, 100, 0), (-5, 100, 10)):
            with self.assertRaises(ValueError):
                fit_view(*args)

    def test_view_transform_is_a_plain_value(self):
        self.assertEqual(ViewTransform(100, 50, 2.0).centre, (50.0, 25.0))


def math_dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


class SnapshotTests(unittest.TestCase):
    def view(self, vid, position, waiting=False, direction=N):
        return VehicleView(vid, direction, position, 4.5, waiting)

    def snap(self, *vehicles, time=0.0):
        return Snapshot(time, {v.id: v for v in vehicles}, {d: SignalColor.RED for d in ALL_DIRECTIONS},
                        Phase.NS, LightStage.GREEN, 10.0, {d: 0 for d in ALL_DIRECTIONS},
                        {d: 0 for d in ALL_DIRECTIONS})

    def test_positions_are_blended(self):
        before, after = self.snap(self.view(1, 10.0)), self.snap(self.view(1, 20.0))
        for alpha, expected in ((0.0, 10.0), (0.25, 12.5), (0.5, 15.0), (1.0, 20.0)):
            self.assertAlmostEqual(interpolate(before, after, alpha)[0].position, expected)

    def test_alpha_is_clamped(self):
        before, after = self.snap(self.view(1, 10.0)), self.snap(self.view(1, 20.0))
        self.assertEqual(interpolate(before, after, -3)[0].position, 10.0)
        self.assertEqual(interpolate(before, after, 9)[0].position, 20.0)

    def test_new_vehicles_are_drawn_where_they_are_and_departed_ones_are_not(self):
        before = self.snap(self.view(1, 10.0), self.view(2, 270.0))
        after = self.snap(self.view(1, 12.0), self.view(3, 5.0))
        drawn = {v.id: v.position for v in interpolate(before, after, 0.5)}
        self.assertEqual(drawn, {1: 11.0, 3: 5.0})

    def test_waiting_flag_switches_half_way(self):
        before, after = self.snap(self.view(1, 10.0, True)), self.snap(self.view(1, 10.5, False))
        self.assertTrue(interpolate(before, after, 0.2)[0].waiting)
        self.assertFalse(interpolate(before, after, 0.8)[0].waiting)

    def test_capture_matches_the_simulator(self):
        settings = make_settings(scenario="rush_hour")
        sim, controller = Simulator(settings), FixedTimeController(settings)
        for _ in range(240):
            controller.act(sim)
            sim.step()
        snap = capture(sim)
        self.assertEqual(snap.time, sim.time)
        self.assertEqual(len(snap.vehicles), sum(r.vehicle_count() for r in sim.roads.values()))
        self.assertEqual(snap.queues, sim.queue_lengths())
        self.assertEqual(snap.signals, sim.light.colors())
        self.assertEqual((snap.phase, snap.stage), (sim.light.phase, sim.light.stage))
        self.assertEqual(snap.outside, {d: len(sim.roads[d].backlog) for d in ALL_DIRECTIONS})
        for v in snap.vehicles.values():
            self.assertTrue(v.direction in ALL_DIRECTIONS and v.length > 0)

    def test_waiting_vehicles_are_those_standing_before_the_stop_line(self):
        settings = make_settings(scenario="rush_hour")
        sim, controller = Simulator(settings), FixedTimeController(settings)
        for _ in range(200):
            controller.act(sim)
            sim.step()
        snap = capture(sim)
        stop_line = settings.simulation.road_length
        expected = sum(1 for r in sim.roads.values() for v in r.vehicles if v.stopped and v.position <= stop_line)
        self.assertEqual(sum(1 for v in snap.vehicles.values() if v.waiting), expected)
        self.assertGreater(expected, 0)


class FakeController(Controller):
    name = "fake"

    def __init__(self):
        self.resets = 0

    def reset(self):
        self.resets += 1

    def act(self, sim):
        pass


class SessionPlaybackTests(unittest.TestCase):
    def session(self, **kwargs):
        settings = make_settings(**{k: kwargs.pop(k) for k in ("duration", "scenario", "seed") if k in kwargs})
        return SimulationSession(settings, FixedTimeController(settings), **kwargs)

    def play(self, session, real_seconds, fps=60):
        for _ in range(int(real_seconds * fps)):
            session.advance(1.0 / fps)

    def test_starts_at_time_zero_with_the_configured_speed(self):
        s = SimulationSession(make_settings(simulation_speed=5.0), FakeController())
        self.assertEqual((s.sim.time, s.speed, s.paused, s.alpha), (0.0, 5.0, False, 0.0))

    def test_speed_argument_overrides_the_setting(self):
        s = SimulationSession(make_settings(simulation_speed=5.0), FakeController(), speed=2.0)
        self.assertEqual(s.speed, 2.0)

    def test_simulation_keeps_pace_with_real_time_at_each_speed(self):
        for speed in SPEED_CHOICES:
            s = self.session(duration=600, speed=speed)
            self.play(s, 2.0)
            self.assertAlmostEqual(s.sim.time, 2.0 * speed, delta=s.dt + 1e-6, msg=f"{speed}x")

    def test_a_long_frame_cannot_make_the_simulation_leap(self):
        s = self.session(duration=600, speed=10.0)
        steps = s.advance(30.0)  # e.g. the window was frozen for 30 s
        self.assertEqual(steps, int(MAX_FRAME_SECONDS * 10 / s.dt))
        self.assertLessEqual(s.sim.time, 1.0 + 1e-9)

    def test_paused_sessions_do_not_move(self):
        s = self.session(paused=True)
        self.assertEqual(s.advance(0.1), 0)
        self.assertEqual(s.sim.time, 0.0)
        s.toggle_pause()
        self.assertFalse(s.paused)
        self.play(s, 1.0)
        self.assertGreater(s.sim.time, 0.0)

    def test_zero_or_negative_time_does_nothing(self):
        s = self.session()
        self.assertEqual((s.advance(0), s.advance(-1.0)), (0, 0))
        self.assertEqual(s.sim.time, 0.0)

    def test_step_once_runs_exactly_one_step_and_shows_the_result(self):
        s = self.session(paused=True)
        self.assertTrue(s.step_once())
        self.assertAlmostEqual(s.sim.time, s.dt)
        self.assertEqual(s.display_time, s.sim.time)
        self.assertIs(s.previous, s.current)
        s.paused = False
        s.advance(0.01)  # resuming must not jump back
        self.assertGreaterEqual(s.display_time, s.sim.time - 1e-9)

    def test_alpha_and_display_time_behave(self):
        s = self.session(duration=600, speed=1.0)
        rng, last = random.Random(3), 0.0
        for _ in range(400):
            s.advance(rng.uniform(0.001, 0.05))
            self.assertTrue(0.0 <= s.alpha <= 1.0)
            self.assertGreaterEqual(s.display_time, last - 1e-9)  # never goes backwards
            self.assertLessEqual(s.display_time, s.sim.time + 1e-9)
            self.assertGreaterEqual(s.display_time, s.sim.time - s.dt - 1e-9)
            last = s.display_time

    def test_finishing(self):
        s = self.session(duration=20, speed=10.0)
        for _ in range(100):
            s.advance(0.1)
        self.assertTrue(s.finished)
        self.assertEqual((s.alpha, s.advance(0.1)), (1.0, 0))
        self.assertFalse(s.step_once())
        self.assertAlmostEqual(s.sim.time, 20.0)

    def test_signals_shown_are_the_ones_vehicles_obey(self):
        s = self.session(duration=200, speed=10.0)
        observed = []
        real_step = s.sim.step

        def spying_step():
            observed.append(s.sim.light.colors())  # just before the step runs
            real_step()

        s.sim.step = spying_step
        for _ in range(600):  # 100 simulated seconds: several signal changes
            before = len(observed)
            s.advance(1 / 60)
            if len(observed) > before:
                self.assertEqual(s.previous.signals, observed[-1])
        self.assertGreater(len(observed), 150)
        distinct = {tuple(sorted((d.value, c.value) for d, c in colors.items())) for colors in observed}
        self.assertGreaterEqual(len(distinct), 4)  # green, yellow, all-red, other phase


class SessionSpeedTests(unittest.TestCase):
    def test_faster_and_slower_walk_through_the_choices_and_stop_at_the_ends(self):
        s = SimulationSession(make_settings(), FakeController(), speed=SPEED_CHOICES[0])
        s.slower()
        self.assertEqual(s.speed, SPEED_CHOICES[0])
        seen = [s.speed]
        for _ in range(10):
            s.faster()
            seen.append(s.speed)
        self.assertEqual(seen[: len(SPEED_CHOICES)], list(SPEED_CHOICES))
        self.assertEqual(s.speed, SPEED_CHOICES[-1])
        s.slower()
        self.assertEqual(s.speed, SPEED_CHOICES[-2])

    def test_invalid_speed(self):
        s = SimulationSession(make_settings(), FakeController())
        for bad in (0, 3.0, -1, 100):
            with self.assertRaises(ValueError):
                s.set_speed(bad)
        with self.assertRaises(ValueError):
            SimulationSession(make_settings(), FakeController(), speed=7.0)


class SessionRestartTests(unittest.TestCase):
    def test_restart_replays_the_same_traffic(self):
        settings = make_settings(duration=60)
        s = SimulationSession(settings, FixedTimeController(settings), speed=10.0)
        for _ in range(100):
            s.advance(0.1)
        first = s.live_metrics()
        s.restart()
        self.assertEqual((s.sim.time, s.collector.steps, s.alpha), (0.0, 0, 0.0))
        for _ in range(100):
            s.advance(0.1)
        self.assertEqual(s.live_metrics(), first)

    def test_restart_resets_the_controller(self):
        controller = FakeController()
        s = SimulationSession(make_settings(), controller)
        self.assertEqual(controller.resets, 1)
        s.restart()
        self.assertEqual(controller.resets, 2)

    def test_new_seed_gives_different_traffic(self):
        settings = make_settings(duration=120)
        s = SimulationSession(settings, FixedTimeController(settings), speed=10.0)
        for _ in range(200):
            s.advance(0.1)
        arrived = s.sim.spawned
        s.new_seed()
        self.assertEqual(s.seed, settings.traffic.seed + 1)
        for _ in range(200):
            s.advance(0.1)
        self.assertNotEqual(s.sim.spawned, arrived)
        self.assertEqual(s.live_metrics().seed, s.seed)

    def test_seed_wraps_around_at_the_maximum(self):
        s = SimulationSession(make_settings(), FakeController())
        s.restart(MAX_SEED)
        s.new_seed()
        self.assertEqual(s.seed, 0)

    def test_restart_with_an_explicit_seed(self):
        s = SimulationSession(make_settings(), FakeController())
        s.restart(seed=77)
        self.assertEqual((s.seed, s.sim.generator.seed), (77, 77))

    def test_invalid_settings_are_refused(self):
        bad = Settings()
        bad.display.fps = 0
        with self.assertRaises(ConfigError):
            SimulationSession(bad, FakeController())


class WatchingChangesNothingTests(unittest.TestCase):
    """Watching a run through the window must give exactly the results of a plain run."""

    def test_pausing_stepping_and_changing_speed_do_not_change_the_results(self):
        settings = make_settings(duration=240, scenario="rush_hour", seed=9)
        plain = run_episode(settings, FixedTimeController(settings)).metrics

        session = SimulationSession(settings, FixedTimeController(settings))
        rng = random.Random(1)
        while not session.finished:
            roll = rng.random()
            if roll < 0.03:
                session.toggle_pause()
            elif roll < 0.06 and session.paused:
                session.step_once()
            elif roll < 0.09:
                rng.choice((session.faster, session.slower))()
            elif roll < 0.10:
                session.paused = False
            session.advance(1 / 60)
            if session.paused and rng.random() < 0.05:
                session.paused = False
        self.assertEqual(session.live_metrics(), plain)


if __name__ == "__main__":
    unittest.main()
