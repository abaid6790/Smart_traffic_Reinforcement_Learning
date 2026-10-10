"""The simulation window: scene + side panel + keyboard and mouse controls.

``SimulationScreen`` holds everything the window does (events, buttons, update, draw)
and works on any pygame surface, so it can be driven by tests and by the screenshot
function without a real window.  ``run_window`` wraps it in an actual window.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pygame

from config.settings import SPEED_CHOICES, Settings
from controllers.base import Controller
from evaluation.metrics import EpisodeMetrics
from ui.components import Button, Fonts
from ui.hud import Hud, PanelData
from ui.scene import SceneRenderer
from ui.session import SimulationSession
from ui.snapshot import interpolate
from ui.theme import get_theme

log = logging.getLogger(__name__)

WINDOW_TITLE = "Smart Traffic Light - Simulation"
_STATS_REFRESH_SECONDS = 0.2

_SPEED_KEYS = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3, pygame.K_5: 4}
_FASTER_KEYS = (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS, pygame.K_UP)
_SLOWER_KEYS = (pygame.K_MINUS, pygame.K_KP_MINUS, pygame.K_DOWN)
_STEP_KEYS = (pygame.K_s, pygame.K_RIGHT, pygame.K_PERIOD)


class SimulationScreen:
    """The whole simulation window, drawable on any surface."""

    def __init__(
        self,
        settings: Settings,
        controller: Controller,
        speed: float | None = None,
        paused: bool = False,
        size: tuple[int, int] | None = None,
        quit_label: str = "Quit",
    ) -> None:
        self.quit_label = quit_label
        self.settings = settings.validate()
        display = self.settings.display
        self.size = size or (display.window_width, display.window_height)
        self.session = SimulationSession(settings, controller, speed=speed, paused=paused)
        self.theme = get_theme(display.theme)
        scale = max(0.67, min(2.0, self.size[1] / 720))
        self.fonts = Fonts(scale)
        self.scene = SceneRenderer(self.settings, self.theme, self.fonts)
        self.hud = Hud(self.theme, self.fonts)

        self.show_help = False
        self.show_stats = display.show_statistics
        self.show_debug = display.show_debug
        self.quit_requested = False
        self.buttons = self._make_buttons()
        self._hover_pos: tuple[int, int] | None = None
        self._metrics: EpisodeMetrics | None = None
        self._metrics_step = -1
        self._metrics_age = 0.0
        self._fps = 0.0

    # ---- layout ----------------------------------------------------------------------------

    @property
    def panel_rect(self) -> pygame.Rect:
        width, height = self.size
        scale = self.fonts.scale
        panel = max(round(300 * max(1.0, scale)), min(round(380 * max(1.0, scale)), round(width * 0.28)))
        return pygame.Rect(width - panel, 0, panel, height)

    @property
    def scene_rect(self) -> pygame.Rect:
        return pygame.Rect(0, 0, self.size[0] - self.panel_rect.width, self.size[1])

    # ---- actions (buttons and keys both call these) -----------------------------------------------

    def toggle_play(self) -> None:
        if self.session.finished:
            self.session.restart()
            self.session.paused = False
        else:
            self.session.toggle_pause()

    def step(self) -> None:
        self.session.paused = True
        self.session.step_once()

    def restart(self) -> None:
        self.session.restart()
        self.session.paused = False

    def new_traffic(self) -> None:
        self.session.new_seed()
        self.session.paused = False

    def toggle_help(self) -> None:
        self.show_help = not self.show_help

    def quit(self) -> None:
        self.quit_requested = True

    def _make_buttons(self) -> list[Button]:
        s = self.session

        def play_label() -> str:
            if s.finished:
                return "Replay"
            return "Play" if s.paused else "Pause"

        return [
            Button(play_label, "Space", "Pause or resume the simulation", self.toggle_play),
            Button("Step", "S", "Run a single step (pauses first)", self.step,
                   enabled=lambda: not s.finished),
            Button("Slower", "-", "Slow the simulation down", s.slower,
                   enabled=lambda: s.speed > SPEED_CHOICES[0]),
            Button("Faster", "+", "Speed the simulation up", s.faster,
                   enabled=lambda: s.speed < SPEED_CHOICES[-1]),
            Button("Restart", "R", "Start this run again with the same traffic", self.restart),
            Button("New traffic", "N", "Start a new run with different traffic", self.new_traffic),
            Button("Help", "H", "Show the keyboard controls", self.toggle_help),
            Button(self.quit_label, "Q", "Leave the simulation", self.quit),
        ]

    # ---- events --------------------------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Deal with one pygame event.  Returns False when the window should close."""
        if event.type == pygame.QUIT:
            self.quit()
        elif event.type == pygame.KEYDOWN:
            self._on_key(event.key)
        elif event.type == pygame.MOUSEMOTION:
            self._hover_pos = event.pos
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._on_click(event.pos)
        return not self.quit_requested

    def _on_key(self, key: int) -> None:
        if key == pygame.K_ESCAPE:
            if self.show_help:
                self.show_help = False
            else:
                self.quit()
        elif key == pygame.K_q:
            self.quit()
        elif key == pygame.K_SPACE:
            self.toggle_play()
        elif key in _STEP_KEYS:
            self.step()
        elif key in _FASTER_KEYS:
            self.session.faster()
        elif key in _SLOWER_KEYS:
            self.session.slower()
        elif key in _SPEED_KEYS:
            self.session.set_speed(SPEED_CHOICES[_SPEED_KEYS[key]])
        elif key == pygame.K_r:
            self.restart()
        elif key == pygame.K_n:
            self.new_traffic()
        elif key in (pygame.K_h, pygame.K_F1, pygame.K_QUESTION):
            self.toggle_help()
        elif key == pygame.K_t:
            self.show_stats = not self.show_stats
        elif key == pygame.K_d:
            self.show_debug = not self.show_debug

    def _on_click(self, pos: tuple[int, int]) -> None:
        if self.show_help and self.scene_rect.collidepoint(pos):
            self.show_help = False  # clicking the help card dismisses it
            return
        for button in self.buttons:
            if button.contains(pos):
                button.click()
                return

    # ---- each frame ----------------------------------------------------------------------------------------

    def update(self, real_seconds: float) -> None:
        """Move the simulation on by ``real_seconds`` and refresh the cached statistics."""
        self.session.advance(real_seconds)
        self._metrics_age += real_seconds
        sim = self.session.sim
        changed = sim.step_count != self._metrics_step
        settled = self.session.paused or self.session.finished
        if self._metrics is None or (changed and (settled or self._metrics_age >= _STATS_REFRESH_SECONDS)):
            self._metrics = self.session.live_metrics()
            self._metrics_step = sim.step_count
            self._metrics_age = 0.0

    def draw(self, surface: pygame.Surface, fps: float | None = None) -> None:
        """Draw the whole window onto ``surface``."""
        if fps is not None:
            self._fps = fps
        session = self.session
        surface.fill(self.theme.background)
        scene_rect, panel_rect = self.scene_rect, self.panel_rect
        vehicles = interpolate(session.previous, session.current, session.alpha)
        self.scene.draw(surface, scene_rect, vehicles, session.state)
        self.hud.draw_legend(surface, scene_rect)

        hovered = next((b for b in self.buttons if self._hover_pos and b.contains(self._hover_pos)), None)
        self.hud.draw_panel(surface, panel_rect, PanelData(
            controller_text=session.controller.describe(),
            scenario=session.sim.settings.traffic.scenario,
            seed=session.seed,
            time=session.display_time,
            duration=self.settings.simulation.duration,
            speed=session.speed,
            paused=session.paused,
            finished=session.finished,
            state=session.state,
            metrics=self._metrics,
            show_stats=self.show_stats,
            buttons=self.buttons,
            hovered=hovered,
            drive_on=self.settings.display.drive_on,
        ))
        if self.show_help:
            self.hud.draw_help(surface, scene_rect, self.settings.display.drive_on)
        elif session.finished and self._metrics is not None:
            self.hud.draw_finished(surface, scene_rect, self._metrics)
        if self.show_debug:
            self.hud.draw_debug(surface, scene_rect, self._debug_lines())

    def _debug_lines(self) -> list[str]:
        s, sim = self.session, self.session.sim
        outside = sum(len(r.backlog) for r in sim.roads.values())
        return [
            f"FPS {self._fps:.0f} (limit {self.settings.display.fps})",
            f"sim time {sim.time:.1f} s   step {sim.step_count}   dt {sim.dt:g} s",
            f"speed {s.speed:g}x   alpha {s.alpha:.2f}",
            f"vehicles {sim.vehicles_in_system()}   waiting outside {outside}",
            f"light {sim.light.describe()}",
        ]


# --------------------------------------------------------------------------------------------------
# Running it
# --------------------------------------------------------------------------------------------------


def run_window(
    settings: Settings,
    controller: Controller,
    speed: float | None = None,
    paused: bool = False,
) -> None:
    """Open the simulation window and run it until the user closes it."""
    pygame.display.init()
    pygame.font.init()
    try:
        display = settings.display
        screen = pygame.display.set_mode((display.window_width, display.window_height))
        pygame.display.set_caption(WINDOW_TITLE)
        window = SimulationScreen(settings, controller, speed=speed, paused=paused,
                                  size=screen.get_size())
        clock = pygame.time.Clock()
        log.info("Simulation window opened (%dx%d)", *screen.get_size())
        running = True
        while running:
            seconds = clock.tick(display.fps) / 1000.0
            for event in pygame.event.get():
                running = window.handle_event(event) and running
            window.update(seconds)
            window.draw(screen, clock.get_fps())
            pygame.display.flip()
        log.info("Simulation window closed")
    finally:
        pygame.quit()


def render_frame(
    settings: Settings,
    controller: Controller,
    after_seconds: float = 120.0,
    size: tuple[int, int] | None = None,
) -> pygame.Surface:
    """Run the simulation for ``after_seconds`` and return a picture of the window.

    Nothing is shown on screen, so this also works on a computer with no display.
    """
    pygame.font.init()
    window = SimulationScreen(settings, controller, paused=True, size=size)
    while window.session.sim.time < after_seconds - 1e-9 and window.session.step_once():
        pass
    window.update(0.0)
    surface = pygame.Surface(window.size)
    window.draw(surface)
    return surface


def save_screenshot(
    path: Path | str,
    settings: Settings,
    controller: Controller,
    after_seconds: float = 120.0,
    size: tuple[int, int] | None = None,
) -> Path:
    """Save a picture of the window as a PNG file and return its path."""
    path = Path(path)
    if path.suffix.lower() != ".png":
        raise ValueError("The screenshot file name must end in .png")
    surface = render_frame(settings, controller, after_seconds, size)
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(surface, str(path))
    log.info("Screenshot saved to %s", path)
    return path
