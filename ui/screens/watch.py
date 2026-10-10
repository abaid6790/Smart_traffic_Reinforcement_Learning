"""Watching one controller: the simulation window, embedded in the application."""

from __future__ import annotations

import pygame

from controllers.fixed_controller import FixedTimeController
from controllers.rl_controller import QLearningController
from ui.app import Screen
from ui.simulation_screen import SimulationScreen


class WatchScreen(Screen):
    name = "watch"

    def __init__(self, app, controller: str = "fixed") -> None:
        super().__init__(app)
        self.kind = controller
        self.inner: SimulationScreen | None = None
        self.error = ""

    def on_enter(self) -> None:
        settings = self.app.settings
        if self.kind == "rl":
            agent = self.app.load_agent()
            if agent is None:
                self.app.notify(self.app.model_status()[1], "warning")
                self.app.go("menu")
                return
            controller = QLearningController(agent)
        else:
            controller = FixedTimeController(settings)
        self.inner = SimulationScreen(settings, controller, size=self.size, quit_label="Menu")

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.inner is None:
            return
        if event.type == pygame.QUIT:
            self.app.quit_requested = True
            return
        self.inner.handle_event(event)
        if self.inner.quit_requested:
            self.app.go("menu")

    def update(self, seconds: float) -> None:
        if self.inner is not None:
            self.inner.size = self.size
            self.inner.update(seconds)

    def draw(self, surface: pygame.Surface) -> None:
        if self.inner is not None:
            self.inner.draw(surface)
