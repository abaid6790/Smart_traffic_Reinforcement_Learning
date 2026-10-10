"""Pieces shared by the training and experiment screens."""

from __future__ import annotations

from collections.abc import Callable

import pygame

from config.settings import SCENARIO_NAMES
from ui.app import Screen
from ui.components import Button


class ScenarioChoice:
    """Seven check buttons plus All / None, backed by a set of chosen scenario names."""

    def __init__(self, screen: Screen, chosen: list[str], enabled: Callable[[], bool]) -> None:
        self.chosen = set(chosen)
        self.buttons: list[Button] = []
        for name in SCENARIO_NAMES:
            self.buttons.append(screen.add(
                lambda n=name: f"[{'x' if n in self.chosen else ' '}] {n}", None, "",
                "Click to include or leave out this traffic scenario",
                lambda n=name: self.toggle(n), enabled))
        self.all_button = screen.add("All", None, "", "Choose every scenario", self.select_all, enabled)
        self.none_button = screen.add("None", None, "", "Clear the choice", self.select_none, enabled)
        self.buttons += [self.all_button, self.none_button]

    def toggle(self, name: str) -> None:
        self.chosen.symmetric_difference_update({name})

    def select_all(self) -> None:
        self.chosen = set(SCENARIO_NAMES)

    def select_none(self) -> None:
        self.chosen = set()

    @property
    def names(self) -> list[str]:
        return [n for n in SCENARIO_NAMES if n in self.chosen]

    def layout(self, x: int, y: int, width: int, s: float, columns: int = 2) -> int:
        """Place the buttons in a grid; returns the y below it."""
        gap, height = round(6 * s), round(34 * s)
        cell = (width - gap * (columns - 1)) // columns
        for index, button in enumerate(self.buttons):
            row, col = divmod(index, columns)
            button.rect = pygame.Rect(x + col * (cell + gap), y + row * (height + gap), cell, height)
        rows = (len(self.buttons) + columns - 1) // columns
        return y + rows * (height + gap)
