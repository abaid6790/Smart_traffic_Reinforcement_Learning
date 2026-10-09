"""The side panel and the overlays (help, run finished, debug) drawn with pygame."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from config.settings import SPEED_CHOICES
from environment.enums import Direction, LightStage, Phase, SignalColor
from evaluation.formatting import format_number
from evaluation.metrics import EpisodeMetrics
from ui.components import Button, Fonts, draw_text, wrap_text
from ui.snapshot import Snapshot
from ui.theme import Theme

_EPS = 1e-9


def format_clock(seconds: float) -> str:
    """Seconds as ``m:ss`` (for example 135 -> ``2:15``)."""
    whole = int(max(0.0, seconds) + _EPS)
    return f"{whole // 60}:{whole % 60:02d}"


@dataclass
class PanelData:
    """Everything the side panel shows."""

    controller_text: str
    scenario: str
    seed: int
    time: float
    duration: float
    speed: float
    paused: bool
    finished: bool
    state: Snapshot
    metrics: EpisodeMetrics | None
    show_stats: bool
    buttons: list[Button]
    hovered: Button | None
    drive_on: str


class Hud:
    """Draws the side panel and overlays."""

    def __init__(self, theme: Theme, fonts: Fonts) -> None:
        self.theme = theme
        self.fonts = fonts

    @property
    def _s(self) -> float:
        return self.fonts.scale

    # ---- the side panel ---------------------------------------------------------------------

    def layout_buttons(self, rect: pygame.Rect, buttons: list[Button]) -> int:
        """Place the buttons in two columns at the bottom of ``rect``.

        Returns the y coordinate of the top of the button area.
        """
        pad = round(14 * self._s)
        gap = round(6 * self._s)
        height = round(38 * self._s)
        width = (rect.width - 2 * pad - gap) // 2
        rows = (len(buttons) + 1) // 2
        top = rect.bottom - pad - round(22 * self._s) - rows * height - (rows - 1) * gap
        for index, button in enumerate(buttons):
            row, column = divmod(index, 2)
            button.rect = pygame.Rect(
                rect.x + pad + column * (width + gap), top + row * (height + gap), width, height)
        return top

    def draw_panel(self, surface: pygame.Surface, rect: pygame.Rect, data: PanelData) -> None:
        theme, fonts, s = self.theme, self.fonts, self._s
        pygame.draw.rect(surface, theme.panel, rect)
        pygame.draw.line(surface, theme.panel_border, rect.topleft, rect.bottomleft)
        pad = round(16 * s)
        x, width = rect.x + pad, rect.width - 2 * pad
        buttons_top = self.layout_buttons(rect, data.buttons)
        limit = buttons_top - round(10 * s)  # nothing may be drawn below this line
        y = rect.y + pad

        # title and controller
        title = fonts.get(32, bold=True)
        if title.size("SMART TRAFFIC LIGHT")[0] > width:
            title = fonts.get(27, bold=True)
        y = draw_text(surface, "SMART TRAFFIC LIGHT", title, theme.accent, (x, y)).bottom + round(4 * s)
        for line in wrap_text(fonts.small, data.controller_text, width, max_lines=3):
            y = draw_text(surface, line, fonts.small, theme.text_dim, (x, y)).bottom + 1
        y += round(6 * s)
        y = draw_text(surface, f"{data.scenario}   |   seed {data.seed}", fonts.body,
                      theme.text, (x, y)).bottom + round(10 * s)

        # clock, progress and status
        clock = draw_text(surface, format_clock(data.time), fonts.big, theme.text, (x, y))
        draw_text(surface, f"/ {format_clock(data.duration)}", fonts.body, theme.text_dim,
                  (clock.right + 8, clock.bottom - 4), "bottomleft")
        status, color = self._status(data)
        status_rect = draw_text(surface, status, fonts.strong, color, (x + width, clock.top), "topright")
        speed_rect = draw_text(surface, f"speed {data.speed:g}x", fonts.body, theme.text_dim,
                               (x + width, status_rect.bottom + 1), "topright")
        y = max(clock.bottom, speed_rect.bottom) + round(8 * s)
        bar = pygame.Rect(x, y, width, round(8 * s))
        pygame.draw.rect(surface, theme.button, bar, border_radius=4)
        done = 0.0 if data.duration <= 0 else min(1.0, data.time / data.duration)
        if done > 0:
            pygame.draw.rect(surface, theme.accent, (bar.x, bar.y, max(6, round(bar.width * done)), bar.height),
                             border_radius=4)
        y = bar.bottom + round(14 * s)

        # signals
        y = self._heading(surface, "SIGNALS", x, y, width)
        y = self._signal_row(surface, ("North / South", "N / S"), Phase.NS, data.state, x, y, width)
        y = self._signal_row(surface, ("East / West", "E / W"), Phase.EW, data.state, x, y, width)
        y += round(10 * s)

        # statistics, as many rows as fit
        if data.show_stats and data.metrics is not None:
            rows = self._stat_rows(data.metrics)
            line = fonts.body.get_height() + round(3 * s)
            if y + fonts.small.get_height() + line <= limit:
                y = self._heading(surface, "THIS RUN", x, y, width)
                for label, value in rows:
                    if y + line > limit:
                        break
                    draw_text(surface, label, fonts.body, theme.text_dim, (x, y))
                    draw_text(surface, value, fonts.strong, theme.text, (x + width, y), "topright")
                    y += line

        # buttons and the hint line under them
        for button in data.buttons:
            button.draw(surface, fonts, theme, hovered=button is data.hovered)
        hint = data.hovered.tooltip if data.hovered is not None else "Press H for help"
        draw_text(surface, hint, fonts.small, theme.text_dim,
                  (rect.centerx, rect.bottom - round(10 * s)), "midbottom")

    def _status(self, data: PanelData) -> tuple[str, tuple[int, int, int]]:
        if data.finished:
            return "FINISHED", self.theme.accent
        if data.paused:
            return "PAUSED", self.theme.warning
        return "RUNNING", self.theme.good

    def _heading(self, surface: pygame.Surface, text: str, x: int, y: int, width: int) -> int:
        rect = draw_text(surface, text, self.fonts.get(20, bold=True), self.theme.text_dim, (x, y))
        line_y = rect.centery
        pygame.draw.line(surface, self.theme.panel_border, (rect.right + 8, line_y), (x + width, line_y))
        return rect.bottom + round(5 * self._s)

    def _signal_row(self, surface: pygame.Surface, names: tuple[str, str], phase: Phase,
                    state: Snapshot, x: int, y: int, width: int) -> int:
        theme, fonts, s = self.theme, self.fonts, self._s
        direction = Direction.NORTH if phase is Phase.NS else Direction.EAST
        signal = state.signals[direction]
        colour = {SignalColor.RED: theme.red, SignalColor.YELLOW: theme.yellow,
                  SignalColor.GREEN: theme.green}[signal]
        size = round(18 * s)
        box = pygame.Rect(x, y + 2, size, size)
        pygame.draw.rect(surface, colour, box, border_radius=4)
        pygame.draw.rect(surface, theme.panel_border, box, width=1, border_radius=4)
        text = signal.value
        if state.stage is LightStage.ALL_RED:
            text += "  (all red)"
        elif state.phase is phase:
            text += f"  {state.stage_time:.0f}s"  # how long this stage has lasted
        room = width - size - 10 - fonts.strong.size(text)[0] - 12
        name = names[0] if fonts.body.size(names[0])[0] <= room else names[1]
        draw_text(surface, name, fonts.body, theme.text, (box.right + 10, y))
        right = draw_text(surface, text, fonts.strong, colour, (x + width, y), "topright")
        return right.bottom + round(5 * s)

    @staticmethod
    def _stat_rows(metrics: EpisodeMetrics) -> list[tuple[str, str]]:
        return [
            ("Vehicles served", str(metrics.vehicles_served)),
            ("Avg wait (served)", format_number(metrics.average_waiting_time, " s")),
            ("Avg queue", format_number(metrics.average_queue_length)),
            ("In the system", str(metrics.vehicles_unserved)),
            ("Vehicles arrived", str(metrics.vehicles_arrived)),
            ("Throughput", format_number(metrics.throughput_per_minute, " /min")),
            ("Light switches", str(metrics.light_switches)),
        ]

    # ---- overlays ------------------------------------------------------------------------------------

    def _card(self, surface: pygame.Surface, area: pygame.Rect, width: int, height: int) -> pygame.Rect:
        """Dim ``area`` and draw an empty card in its middle; return the card rectangle."""
        shade = pygame.Surface(area.size, pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        surface.blit(shade, area.topleft)
        width, height = min(width, area.width - 24), min(height, area.height - 24)
        card = pygame.Rect(0, 0, width, height)
        card.center = area.center
        pygame.draw.rect(surface, self.theme.panel, card, border_radius=12)
        pygame.draw.rect(surface, self.theme.accent, card, width=2, border_radius=12)
        return card

    def draw_help(self, surface: pygame.Surface, area: pygame.Rect, drive_on: str) -> None:
        theme, fonts, s = self.theme, self.fonts, self._s
        speeds = " ".join(f"{i + 1}={v:g}x" for i, v in enumerate(SPEED_CHOICES))
        controls = [
            ("Space", "pause / play  (replay when finished)"),
            ("S  or  Right", "run one step (pauses first)"),
            ("+  /  -", "faster / slower"),
            ("1 - 5", f"pick a speed:  {speeds}"),
            ("R", "restart this run, same traffic"),
            ("N", "new traffic (next seed)"),
            ("T", "show / hide statistics"),
            ("D", "show / hide debug information"),
            ("H", "show / hide this help"),
            ("Esc  or  Q", "quit"),
        ]
        pad, key_width = round(20 * s), round(150 * s)
        width = min(round(560 * s), area.width - 24)
        text_width = width - 2 * pad - key_width
        rows = [(keys, wrap_text(fonts.body, text, text_width, max_lines=3)) for keys, text in controls]
        row_gap, body_h = round(5 * s), fonts.body.get_height()
        footer = wrap_text(fonts.small, f"Vehicles keep to the {drive_on}.  Signals always show "
                           "their colour's name.", width - 2 * pad, max_lines=2)
        height = (round(16 * s) + fonts.title.get_height() + round(8 * s)
                  + sum(len(lines) * body_h + row_gap for _, lines in rows) + round(6 * s)
                  + 2 * (body_h + round(3 * s)) + round(4 * s)
                  + len(footer) * fonts.small.get_height() + round(16 * s))
        card = self._card(surface, area, width, height)
        x, y = card.x + pad, card.y + round(16 * s)
        y = draw_text(surface, "HELP", fonts.title, theme.accent, (x, y)).bottom + round(8 * s)
        for (keys, _), (_, lines) in zip(controls, rows):
            draw_text(surface, keys, fonts.strong, theme.text, (x, y))
            for line in lines:
                y = draw_text(surface, line, fonts.body, theme.text_dim, (x + key_width, y)).bottom
            y += row_gap
        y += round(6 * s)
        legend = [(theme.vehicle_moving, "moving"), (theme.vehicle_waiting, "waiting at a red light")]
        for colour, text in legend:
            swatch = pygame.Rect(x, y + 3, round(22 * s), round(12 * s))
            pygame.draw.rect(surface, colour, swatch, border_radius=3)
            pygame.draw.rect(surface, theme.vehicle_outline, swatch, width=1, border_radius=3)
            y = draw_text(surface, text, fonts.body, theme.text, (swatch.right + 10, y)).bottom + round(3 * s)
        y += round(4 * s)
        for line in footer:
            y = draw_text(surface, line, fonts.small, theme.text_dim, (x, y)).bottom

    def draw_finished(self, surface: pygame.Surface, area: pygame.Rect, metrics: EpisodeMetrics) -> None:
        theme, fonts, s = self.theme, self.fonts, self._s
        rows = [
            ("Vehicles served", f"{metrics.vehicles_served} of {metrics.vehicles_arrived} arrived"),
            ("Average waiting time", format_number(metrics.average_waiting_time, " s")),
            ("  including those still waiting", format_number(metrics.average_waiting_time_all, " s")),
            ("Average queue length", format_number(metrics.average_queue_length, " vehicles")),
            ("Maximum queue length", f"{metrics.max_queue_length} vehicles"),
            ("Average travel time", format_number(metrics.average_travel_time, " s")),
            ("Average stops per vehicle", format_number(metrics.average_stops, digits=2)),
            ("Throughput", format_number(metrics.throughput_per_minute, " vehicles / min")),
        ]
        line = fonts.body.get_height() + round(5 * s)
        height = (round(16 * s) + fonts.title.get_height() + fonts.small.get_height() + round(14 * s)
                  + len(rows) * line + round(4 * s) + fonts.small.get_height()
                  + round(24 * s) + fonts.strong.get_height() + round(18 * s))
        card = self._card(surface, area, round(560 * s), height)
        x, y = card.x + round(22 * s), card.y + round(16 * s)
        y = draw_text(surface, "RUN FINISHED", fonts.title, theme.accent, (x, y)).bottom + round(2 * s)
        y = draw_text(surface, f"{metrics.controller} controller  |  {metrics.scenario}  |  seed {metrics.seed}",
                      fonts.small, theme.text_dim, (x, y)).bottom + round(12 * s)
        for label, value in rows:
            draw_text(surface, label, fonts.body, theme.text_dim, (x, y))
            draw_text(surface, value, fonts.strong, theme.text, (card.right - round(22 * s), y), "topright")
            y += line
        safety = "passed" if metrics.safety_violations == 0 else f"FAILED ({metrics.safety_violations} steps)"
        y += round(4 * s)
        draw_text(surface, f"Safety check (no crossing conflicts): {safety}", fonts.small,
                  theme.good if metrics.safety_violations == 0 else theme.red, (x, y))
        draw_text(surface, "R  replay        N  new traffic        Q  quit", fonts.strong, theme.text,
                  (card.centerx, card.bottom - round(18 * s)), "midbottom")

    def draw_legend(self, surface: pygame.Surface, area: pygame.Rect) -> None:
        """A small key to the vehicle colours in the corner of the scene."""
        theme, fonts, s = self.theme, self.fonts, self._s
        x, y = area.x + round(12 * s), area.bottom - round(12 * s)
        for colour, text in reversed([(theme.vehicle_moving, "moving"),
                                      (theme.vehicle_waiting, "waiting")]):
            swatch = pygame.Rect(x, 0, round(20 * s), round(11 * s))
            label = fonts.small.render(text, True, theme.text_dim)
            swatch.bottom = y - 2
            pygame.draw.rect(surface, colour, swatch, border_radius=3)
            pygame.draw.rect(surface, theme.vehicle_outline, swatch, width=1, border_radius=3)
            surface.blit(label, (swatch.right + 8, y - label.get_height()))
            y -= label.get_height() + 3

    def draw_debug(self, surface: pygame.Surface, area: pygame.Rect, lines: list[str]) -> None:
        fonts, s = self.fonts, self._s
        y = area.y + round(10 * s)
        for line in lines:
            text = fonts.small.render(line, True, (235, 238, 242))  # light text on a dark strip, any theme
            background = pygame.Rect(area.x + round(8 * s), y, text.get_width() + 8, text.get_height() + 2)
            shade = pygame.Surface(background.size, pygame.SRCALPHA)
            shade.fill((0, 0, 0, 185))
            surface.blit(shade, background.topleft)
            surface.blit(text, (background.x + 4, background.y + 1))
            y = background.bottom + 2
