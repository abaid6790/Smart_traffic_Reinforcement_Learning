"""The About screen."""

from __future__ import annotations

import pygame

from config.settings import PROJECT_NAME, PROJECT_VERSION
from ui.app import Screen
from ui.components import draw_text, wrap_text

PARAGRAPHS = (
    "A simulated four-way intersection. A traditional fixed-time light and a Q-Learning agent "
    "(a very small form of reinforcement learning) control it, and the program compares them "
    "fairly: every controller gets exactly the same traffic.",
    "The agent sees 18 situations (how busy North/South and East/West are, and which road has green) "
    "and chooses KEEP or SWITCH. It is rewarded for reducing waiting vehicles and punished for "
    "switching too often. The light itself enforces minimum green, maximum green, yellow and all-red, "
    "so the agent can never create an unsafe signal.",
    "A fair comparison also includes a tuned fixed-time light, because the default 30 s timer is weak. "
    "Results show confidence intervals and say 'no clear difference' when the data cannot tell.",
    "Educational simulation only. It must never be connected to real traffic-control equipment. "
    "Everything runs offline and nothing is sent anywhere. Technical details go to logs/application.log.",
)


class AboutScreen(Screen):
    name = "about"
    heading = "About"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.add("Back", pygame.K_b, "Esc", "Return to the main menu", self.back)

    def layout(self, size: tuple[int, int]) -> None:
        s = self.s
        self.buttons[0].rect = pygame.Rect(round(28 * s), size[1] - round(78 * s), round(160 * s), round(46 * s))

    def draw_content(self, surface: pygame.Surface) -> None:
        theme, fonts, s = self.theme, self.fonts, self.s
        x, width = round(28 * s), min(self.size[0] - round(56 * s), round(900 * s))
        y = draw_text(surface, PROJECT_NAME, fonts.strong, theme.text, (x, round(80 * s))).bottom + 4
        y = draw_text(surface, f"Version {PROJECT_VERSION}   |   MIT licence", fonts.small, theme.text_dim,
                      (x, y)).bottom + round(14 * s)
        for text in PARAGRAPHS:
            for line in wrap_text(fonts.body, text, width):
                y = draw_text(surface, line, fonts.body, theme.text, (x, y)).bottom + 2
            y += round(10 * s)
        paths = self.app.paths
        for label, value in (("Model file", paths.model_path), ("Results folder", paths.results_dir),
                             ("Settings file", paths.settings_file)):
            y = draw_text(surface, f"{label}: {value}", fonts.small, theme.text_dim, (x, y)).bottom + 3
