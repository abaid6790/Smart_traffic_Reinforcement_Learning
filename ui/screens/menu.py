"""The main menu."""

from __future__ import annotations

import pygame

from ui.app import Screen
from ui.components import draw_text, wrap_text
from ui.results_data import list_experiments


class MenuScreen(Screen):
    name = "menu"
    heading = "Smart Traffic Light Control"

    def __init__(self, app) -> None:
        super().__init__(app)
        has_model = lambda: self.app.model_status()[0] == "ok"  # noqa: E731
        go = lambda target: (lambda: self.request_leave(target))  # noqa: E731
        self.watch_fixed = self.add("Watch fixed-time light", pygame.K_1, "1",
                                    "Watch the traditional timer control the intersection", go("watch_fixed"))
        self.watch_rl = self.add("Watch Q-Learning agent", pygame.K_2, "2",
                                 "Watch the trained agent control the intersection", go("watch_rl"), has_model)
        self.compare = self.add("Compare side by side", pygame.K_3, "3",
                                "Fixed-time and trained agent on exactly the same traffic", go("compare"), has_model)
        self.train = self.add("Train the agent", pygame.K_4, "4",
                              "Let the agent practise on simulated traffic and save its model", go("training"))
        self.experiment = self.add("Run an experiment", pygame.K_5, "5",
                                   "Compare all controllers over many runs and save the results", go("experiment"))
        self.results = self.add("View results", pygame.K_6, "6",
                                "Tables and graphs of saved experiments and training runs", go("results"))
        self.settings = self.add("Settings", pygame.K_7, "7",
                                 "Change traffic, lights, learning and display options", go("settings"))
        self.about = self.add("About", pygame.K_8, "8", "What this program is and how it works", go("about"))
        self.quit_button = self.add("Quit", pygame.K_q, "Q", "Close the program", go("quit"))
        self._results_count = 0

    def on_enter(self) -> None:
        self._results_count = sum(1 for e in list_experiments(self.app.paths.results_dir) if e.ok)

    def update(self, seconds: float) -> None:
        reason = self.app.model_status()[1]
        for button in (self.watch_rl, self.compare):
            button.tooltip = (
                "Watch the trained agent control the intersection" if button is self.watch_rl
                else "Fixed-time and trained agent on exactly the same traffic")
            if not button.enabled:
                button.tooltip = f"Not available: {reason}"

    def layout(self, size: tuple[int, int]) -> None:
        s = self.s
        x, y = round(28 * s), round(86 * s)
        width, height, gap = round(380 * s), round(50 * s), round(10 * s)
        for button in self.buttons:
            button.rect = pygame.Rect(x, y, width, height)
            y += height + gap + (round(14 * s) if button is self.about else 0)

    def draw_content(self, surface: pygame.Surface) -> None:
        theme, fonts, s = self.theme, self.fonts, self.s
        app, settings = self.app, self.app.settings
        card = pygame.Rect(round(450 * s), round(86 * s), self.size[0] - round(450 * s) - round(28 * s),
                           round(330 * s))
        pygame.draw.rect(surface, theme.panel, card, border_radius=10)
        pygame.draw.rect(surface, theme.panel_border, card, width=1, border_radius=10)
        x, y = card.x + round(20 * s), card.y + round(16 * s)
        y = draw_text(surface, "Current setup", fonts.strong, theme.accent, (x, y)).bottom + round(10 * s)
        status, text = app.model_status()
        lines = [
            ("Traffic scenario", settings.traffic.scenario),
            ("Random seed", str(settings.traffic.seed)),
            ("Run length", f"{settings.simulation.duration:g} s"),
            ("Fixed-time greens", f"NS {settings.fixed.ns_green:g} s / EW {settings.fixed.ew_green:g} s"),
            ("Saved experiments", str(self._results_count)),
        ]
        for label, value in lines:
            draw_text(surface, label, fonts.body, theme.text_dim, (x, y))
            y = draw_text(surface, value, fonts.body, theme.text, (card.right - round(20 * s), y),
                          "topright").bottom + round(6 * s)
        y += round(8 * s)
        color = theme.good if status == "ok" else theme.warning
        for line in wrap_text(fonts.body, text, card.width - round(40 * s), 3):
            y = draw_text(surface, line, fonts.body, color, (x, y)).bottom + 2
        note = ("Educational simulation only. It must never be connected to real traffic-control equipment.")
        y = card.bottom + round(18 * s)
        for line in wrap_text(fonts.small, note, card.width, 3):
            y = draw_text(surface, line, fonts.small, theme.text_dim, (card.x, y)).bottom + 2
