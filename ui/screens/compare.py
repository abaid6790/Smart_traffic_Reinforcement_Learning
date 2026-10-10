"""Side by side: the fixed-time light and the trained agent on exactly the same traffic."""

from __future__ import annotations

import pygame

from config.settings import SPEED_CHOICES
from controllers.fixed_controller import FixedTimeController
from controllers.rl_controller import QLearningController
from evaluation.metrics import improvement_percent
from ui.app import Screen
from ui.components import draw_text
from ui.hud import format_clock
from ui.scene import SceneRenderer
from ui.session import SimulationSession
from ui.snapshot import interpolate


class CompareScreen(Screen):
    name = "compare"
    heading = "Compare side by side"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.sessions: list[SimulationSession] = []
        self.renderers: list[SceneRenderer] = []
        self.titles = ("Fixed-time light", "Q-Learning agent")
        self.metrics = [None, None]
        self._age = 1.0
        s = lambda: self.sessions  # noqa: E731
        self.add(lambda: "Replay" if self.finished else ("Play" if self.paused else "Pause"),
                 pygame.K_SPACE, "Space", "Pause or resume both simulations", self.toggle_play)
        self.add("Step", pygame.K_s, "S", "Run one step on both (pauses first)", self.step,
                 lambda: not self.finished)
        self.add("Slower", pygame.K_MINUS, "-", "Slow both simulations down", lambda: self._speed(-1),
                 lambda: bool(s()) and s()[0].speed > SPEED_CHOICES[0])
        self.add("Faster", pygame.K_PLUS, "+", "Speed both simulations up", lambda: self._speed(1),
                 lambda: bool(s()) and s()[0].speed < SPEED_CHOICES[-1])
        self.add("Restart", pygame.K_r, "R", "Run the same traffic again", self.restart)
        self.add("New traffic", pygame.K_n, "N", "Both controllers get the next traffic seed", self.new_traffic)
        self.add("Menu", pygame.K_q, "Esc", "Back to the main menu", self.back)
        self._keys[pygame.K_EQUALS] = self.buttons[3]
        self._keys[pygame.K_KP_PLUS] = self.buttons[3]
        self._keys[pygame.K_KP_MINUS] = self.buttons[2]

    # ---- state -------------------------------------------------------------------------------------

    def on_enter(self) -> None:
        settings = self.app.settings
        agent = self.app.load_agent()
        if agent is None:
            self.app.notify(self.app.model_status()[1], "warning")
            self.app.go("menu")
            return
        controllers = (FixedTimeController(settings), QLearningController(agent))
        self.sessions = [SimulationSession(settings, c) for c in controllers]
        self.renderers = [SceneRenderer(settings, self.theme, self.fonts) for _ in controllers]
        self._refresh_metrics()

    @property
    def finished(self) -> bool:
        return bool(self.sessions) and all(x.finished for x in self.sessions)

    @property
    def paused(self) -> bool:
        return bool(self.sessions) and self.sessions[0].paused

    def toggle_play(self) -> None:
        if self.finished:
            self.restart()
            return
        for session in self.sessions:
            session.toggle_pause()
        paused = self.sessions[0].paused
        for session in self.sessions:
            session.paused = paused

    def step(self) -> None:
        for session in self.sessions:
            session.paused = True
            session.step_once()
        self._refresh_metrics()

    def restart(self) -> None:
        for session in self.sessions:
            session.restart()
            session.paused = False
        self._refresh_metrics()

    def new_traffic(self) -> None:
        for session in self.sessions:
            session.new_seed()
            session.paused = False
        self._refresh_metrics()

    def _speed(self, direction: int) -> None:
        for session in self.sessions:
            session.faster() if direction > 0 else session.slower()

    def _refresh_metrics(self) -> None:
        self.metrics = [session.live_metrics() for session in self.sessions]
        self._age = 0.0

    def update(self, seconds: float) -> None:
        for session in self.sessions:
            session.advance(seconds)
        self._age += seconds
        if self._age >= 0.2 or self.finished or self.paused:
            self._refresh_metrics()

    # ---- drawing ---------------------------------------------------------------------------------------

    def layout(self, size: tuple[int, int]) -> None:
        s = self.s
        gap = round(8 * s)
        height = round(44 * s)
        width = (size[0] - round(56 * s) - gap * (len(self.buttons) - 1)) // len(self.buttons)
        y = size[1] - round(44 * s) - height
        for i, button in enumerate(self.buttons):
            button.rect = pygame.Rect(round(28 * s) + i * (width + gap), y, width, height)

    def _panes(self) -> list[pygame.Rect]:
        s = self.s
        top, bottom = round(72 * s), self.buttons[0].rect.top - round(36 * s)
        total = self.size[0] - round(56 * s)
        half = (total - round(14 * s)) // 2
        return [pygame.Rect(round(28 * s) + i * (half + round(14 * s)), top, half, bottom - top)
                for i in range(2)]

    def draw_content(self, surface: pygame.Surface) -> None:
        if not self.sessions:
            return
        theme, fonts, s = self.theme, self.fonts, self.s
        strip = round(86 * s)
        for index, pane in enumerate(self._panes()):
            session, renderer, m = self.sessions[index], self.renderers[index], self.metrics[index]
            scene_rect = pygame.Rect(pane.x, pane.y, pane.width, pane.height - strip)
            pygame.draw.rect(surface, theme.panel, pane, border_radius=8)
            vehicles = interpolate(session.previous, session.current, session.alpha)
            clip = surface.get_clip()
            surface.set_clip(scene_rect)
            renderer.draw(surface, scene_rect, vehicles, session.state)
            surface.set_clip(clip)
            pygame.draw.rect(surface, theme.accent if index else theme.panel_border, pane, width=2, border_radius=8)
            draw_text(surface, self.titles[index], fonts.strong, theme.text, (pane.x + 12, pane.y + 8))
            draw_text(surface, f"{format_clock(session.display_time)} / "
                      f"{format_clock(self.app.settings.simulation.duration)}   {session.speed:g}x",
                      fonts.small, theme.text_dim, (pane.right - 12, pane.y + 12), "topright")
            y = scene_rect.bottom + round(8 * s)
            if m is not None:
                wait = m.average_waiting_time_all
                text = (f"Avg wait {wait:.1f} s" if wait is not None else "Avg wait n/a")
                draw_text(surface, text, fonts.strong, theme.text, (pane.x + 12, y))
                queue = m.average_queue_length
                draw_text(surface, f"queue {'n/a' if queue is None else format(queue, '.1f')}   "
                          f"served {m.vehicles_served}   switches {m.light_switches}", fonts.body, theme.text_dim,
                          (pane.x + 12, y + round(30 * s)))
        self._draw_verdict(surface)

    def _draw_verdict(self, surface: pygame.Surface) -> None:
        fixed, rl = self.metrics
        if fixed is None or rl is None:
            return
        theme, fonts, s = self.theme, self.fonts, self.s
        seed = self.sessions[0].seed
        if self.finished:
            gain = improvement_percent(fixed.average_waiting_time_all, rl.average_waiting_time_all)
            text = ("Finished: " + ("waiting time n/a" if gain is None else
                    f"the agent's average waiting time is {abs(gain):.1f} % "
                    f"{'lower' if gain >= 0 else 'higher'} than the fixed-time light's")
                    + f" (seed {seed}). One run is not proof; see Run an experiment for statistics.")
        else:
            text = f"Both controllers see exactly the same cars (scenario {self.app.settings.traffic.scenario}, seed {seed})."
        draw_text(surface, text, fonts.small, theme.warning if self.finished else theme.text_dim,
                  (round(28 * s), self.buttons[0].rect.top - round(6 * s)), "bottomleft")
