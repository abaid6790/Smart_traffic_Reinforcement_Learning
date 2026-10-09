"""Tests of the pygame window, run without a display (SDL "dummy" video driver)."""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

try:
    import pygame
except ImportError:  # pragma: no cover - only when pygame is not installed
    pygame = None

from config.settings import SPEED_CHOICES, Settings
from controllers.fixed_controller import FixedTimeController

if pygame is not None:
    from ui.components import Button, Fonts, wrap_text
    from ui.simulation_screen import SimulationScreen, render_frame, save_screenshot


def make_settings(**sections):
    base = Settings()
    changes = {"simulation": {"duration": 120.0}, "traffic": {"scenario": "rush_hour", "seed": 7}}
    for name, values in sections.items():
        changes.setdefault(name, {}).update(values)
    return base.updated(**changes)


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


def click(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)


@unittest.skipIf(pygame is None, "pygame is not installed")
class WindowTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.font.init()

    def screen(self, size=(1280, 720), **kw):
        settings = kw.pop("settings", None) or make_settings()
        return SimulationScreen(settings, FixedTimeController(settings), size=size, **kw)

    def drawn(self, window):
        surface = pygame.Surface(window.size)
        window.draw(surface)
        return surface


class DrawingTests(WindowTestCase):
    def test_draws_at_several_sizes_themes_and_sides(self):
        for size in ((640, 480), (1280, 720), (1920, 1080), (900, 900)):
            for theme in ("dark", "light"):
                for side in ("right", "left"):
                    settings = make_settings(display={"theme": theme, "drive_on": side})
                    window = self.screen(size, settings=settings, paused=True)
                    for _ in range(100):
                        window.session.step_once()
                    window.update(0.0)
                    surface = self.drawn(window)
                    self.assertEqual(surface.get_size(), size)

    def test_view_ranges_draw(self):
        for view_range in (30.0, 60.0, 300.0):
            window = self.screen(settings=make_settings(display={"view_range": view_range}), paused=True)
            self.drawn(window)

    def test_the_picture_is_not_blank_and_changes_over_time(self):
        window = self.screen(paused=True)
        first = pygame.image.tobytes(self.drawn(window), "RGB")
        self.assertGreater(len(set(first[::97])), 5)  # more than a flat colour
        for _ in range(60):
            window.session.step_once()
        second = pygame.image.tobytes(self.drawn(window), "RGB")
        self.assertNotEqual(first, second)

    def test_help_finish_stats_and_debug_overlays_draw(self):
        window = self.screen(paused=True)
        plain = pygame.image.tobytes(self.drawn(window), "RGB")
        window.toggle_help()
        self.assertNotEqual(plain, pygame.image.tobytes(self.drawn(window), "RGB"))
        window.toggle_help()
        window.handle_event(key(pygame.K_d))
        self.assertTrue(window.show_debug)
        self.assertNotEqual(plain, pygame.image.tobytes(self.drawn(window), "RGB"))
        window.handle_event(key(pygame.K_t))
        self.assertFalse(window.show_stats)
        self.drawn(window)
        while window.session.step_once():
            pass
        window.update(0.0)
        self.assertTrue(window.session.finished)
        self.drawn(window)

    def test_panel_and_scene_fit_in_the_window(self):
        for size in ((640, 480), (1280, 720), (1920, 1080)):
            window = self.screen(size)
            panel, scene = window.panel_rect, window.scene_rect
            self.assertEqual(panel.left, scene.right)
            self.assertEqual(panel.right, size[0])
            self.assertGreater(scene.width, panel.width)


class ControlTests(WindowTestCase):
    def test_space_pauses_and_resumes(self):
        window = self.screen()
        self.assertFalse(window.session.paused)
        window.handle_event(key(pygame.K_SPACE))
        self.assertTrue(window.session.paused)
        window.handle_event(key(pygame.K_SPACE))
        self.assertFalse(window.session.paused)

    def test_step_runs_one_step_and_pauses(self):
        window = self.screen()
        before = window.session.sim.step_count
        window.handle_event(key(pygame.K_s))
        self.assertEqual(window.session.sim.step_count, before + 1)
        self.assertTrue(window.session.paused)

    def test_speed_keys(self):
        window = self.screen()
        for number, expected in zip(range(1, 6), SPEED_CHOICES):
            window.handle_event(key(getattr(pygame, f"K_{number}")))
            self.assertEqual(window.session.speed, expected)
        window.handle_event(key(pygame.K_MINUS))
        self.assertEqual(window.session.speed, SPEED_CHOICES[-2])
        window.handle_event(key(pygame.K_PLUS))
        self.assertEqual(window.session.speed, SPEED_CHOICES[-1])
        window.handle_event(key(pygame.K_PLUS))  # already at the top: stays valid
        self.assertEqual(window.session.speed, SPEED_CHOICES[-1])

    def test_restart_keeps_the_seed_and_new_traffic_changes_it(self):
        window = self.screen(paused=True)
        seed = window.session.seed
        for _ in range(20):
            window.session.step_once()
        window.handle_event(key(pygame.K_r))
        self.assertEqual((window.session.seed, window.session.sim.step_count), (seed, 0))
        window.handle_event(key(pygame.K_n))
        self.assertNotEqual(window.session.seed, seed)

    def test_help_toggle_and_escape_order(self):
        window = self.screen()
        window.handle_event(key(pygame.K_h))
        self.assertTrue(window.show_help)
        self.assertTrue(window.handle_event(key(pygame.K_ESCAPE)))  # closes help only
        self.assertFalse(window.show_help)
        self.assertFalse(window.handle_event(key(pygame.K_ESCAPE)))  # now quits

    def test_quit_keys_and_window_close(self):
        self.assertFalse(self.screen().handle_event(key(pygame.K_q)))
        self.assertFalse(self.screen().handle_event(pygame.event.Event(pygame.QUIT)))

    def test_every_button_is_clickable_and_does_what_it_says(self):
        window = self.screen(paused=True)
        self.drawn(window)  # buttons get their rectangles when drawn
        by_label = {b.label: b for b in window.buttons}
        self.assertEqual(len(window.buttons), 8)
        for button in window.buttons:
            self.assertGreater(button.rect.width * button.rect.height, 0, button.label)
            self.assertTrue(window.panel_rect.contains(button.rect), button.label)

        window.handle_event(click(by_label["Play"].rect.center))
        self.assertFalse(window.session.paused)
        window.handle_event(click(window.buttons[0].rect.center))
        self.assertTrue(window.session.paused)
        steps = window.session.sim.step_count
        window.handle_event(click(by_label["Step"].rect.center))
        self.assertEqual(window.session.sim.step_count, steps + 1)
        speed = window.session.speed
        window.handle_event(click(by_label["Faster"].rect.center))
        self.assertGreater(window.session.speed, speed)
        window.handle_event(click(by_label["Slower"].rect.center))
        self.assertEqual(window.session.speed, speed)
        window.handle_event(click(by_label["Help"].rect.center))
        self.assertTrue(window.show_help)
        window.handle_event(click(window.scene_rect.center))  # click the card to close
        self.assertFalse(window.show_help)
        seed = window.session.seed
        window.handle_event(click(by_label["New traffic"].rect.center))
        self.assertNotEqual(window.session.seed, seed)
        window.handle_event(click(by_label["Restart"].rect.center))
        self.assertEqual(window.session.sim.step_count, 0)
        self.assertFalse(window.handle_event(click(by_label["Quit"].rect.center)))

    def test_disabled_buttons_do_nothing_and_replay_restarts(self):
        window = self.screen(paused=True)
        window.session.set_speed(SPEED_CHOICES[0])
        slower = next(b for b in window.buttons if b.label == "Slower")
        self.assertFalse(slower.click())
        self.assertEqual(window.session.speed, SPEED_CHOICES[0])
        while window.session.step_once():
            pass
        self.assertEqual(window.buttons[0].label, "Replay")
        self.assertFalse(next(b for b in window.buttons if b.label == "Step").enabled)
        window.handle_event(key(pygame.K_SPACE))
        self.assertFalse(window.session.finished)
        self.assertFalse(window.session.paused)

    def test_mouse_move_sets_hover_and_other_clicks_are_ignored(self):
        window = self.screen(paused=True)
        self.drawn(window)
        window.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=window.buttons[0].rect.center,
                                               rel=(0, 0), buttons=(0, 0, 0)))
        self.drawn(window)
        steps = window.session.sim.step_count
        window.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=3,
                                               pos=window.buttons[1].rect.center))
        self.assertEqual(window.session.sim.step_count, steps)

    def test_update_moves_time_forward_unless_paused(self):
        window = self.screen()
        for _ in range(6):
            window.update(0.1)  # 0.6 s is more than one 0.5 s step
        self.assertGreater(window.session.sim.time, 0)
        window.session.paused = True
        t = window.session.sim.time
        window.update(0.1)
        self.assertEqual(window.session.sim.time, t)

    def test_watching_does_not_change_the_results(self):
        from simulation.runner import run_episode
        settings = make_settings()
        window = SimulationScreen(settings, FixedTimeController(settings), speed=10.0)
        guard = 0
        while not window.session.finished and guard < 100000:
            window.update(0.05)
            guard += 1
        reference = run_episode(settings, FixedTimeController(settings)).metrics
        self.assertEqual(window.session.live_metrics(), reference)


class SignalDrawingTests(WindowTestCase):
    def count(self, surface, color):
        pixels = pygame.image.tobytes(surface, "RGB")
        needle = bytes(color)
        return sum(1 for i in range(0, len(pixels), 3) if pixels[i:i + 3] == needle)

    def test_a_signal_head_lights_only_the_current_colour(self):
        from environment.enums import ALL_DIRECTIONS, SignalColor
        window = self.screen((800, 600))
        window.scene._prepare((560, 600))
        theme = window.theme
        colours = {SignalColor.RED: theme.red, SignalColor.YELLOW: theme.yellow,
                   SignalColor.GREEN: theme.green}
        for direction in ALL_DIRECTIONS:
            counts = {}
            for signal in colours:
                surface = pygame.Surface((560, 600))
                surface.fill(theme.ground)
                window.scene._draw_signal(surface, direction, signal)
                counts[signal] = {s: self.count(surface, c) for s, c in colours.items()}
            for signal in colours:
                lit = counts[signal][signal]
                others = [counts[signal][o] for o in colours if o is not signal]
                self.assertGreater(lit, 0, (direction, signal))
                self.assertEqual(others, [0, 0], (direction, signal, counts[signal]))  # no other lamp is lit

    def test_the_scene_shows_the_real_signal_state(self):
        window = self.screen(paused=True)
        window.session.step_once()
        state = window.session.state
        surface = self.drawn(window)
        self.assertGreater(self.count(surface, window.theme.green), 0)
        self.assertGreater(self.count(surface, window.theme.red), 0)
        self.assertEqual(len(state.signals), 4)


class ComponentTests(WindowTestCase):
    def test_wrap_text(self):
        font = Fonts(1.0).get(20)
        lines = wrap_text(font, "one two three four five six seven eight nine ten", 120)
        self.assertGreater(len(lines), 1)
        self.assertTrue(all(font.size(line)[0] <= 120 for line in lines))
        self.assertEqual(" ".join(lines), "one two three four five six seven eight nine ten")
        capped = wrap_text(font, "one two three four five six seven eight nine ten", 120, max_lines=2)
        self.assertEqual(len(capped), 2)
        self.assertTrue(capped[-1].endswith("..."))
        self.assertEqual(wrap_text(font, "", 100), [])

    def test_button_label_and_enabled_can_be_functions(self):
        state = {"on": False}
        calls = []
        button = Button(lambda: "On" if state["on"] else "Off", "X", "tip",
                        lambda: calls.append(1), enabled=lambda: state["on"])
        self.assertEqual(button.label, "Off")
        self.assertFalse(button.click())
        state["on"] = True
        self.assertEqual(button.label, "On")
        self.assertTrue(button.click())
        self.assertEqual(calls, [1])


class ScreenshotTests(WindowTestCase):
    def test_save_screenshot_writes_a_png(self):
        settings = make_settings()
        with tempfile.TemporaryDirectory() as tmp:
            path = save_screenshot(Path(tmp) / "sub" / "frame.png", settings,
                                   FixedTimeController(settings), after_seconds=60, size=(800, 450))
            self.assertTrue(path.is_file())
            image = pygame.image.load(str(path))
            self.assertEqual(image.get_size(), (800, 450))

    def test_screenshot_must_be_a_png(self):
        settings = make_settings()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                save_screenshot(Path(tmp) / "frame.jpg", settings, FixedTimeController(settings))
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_render_frame_shows_the_requested_time(self):
        settings = make_settings()
        surface = render_frame(settings, FixedTimeController(settings), after_seconds=30, size=(640, 480))
        self.assertEqual(surface.get_size(), (640, 480))


if __name__ == "__main__":
    unittest.main()
