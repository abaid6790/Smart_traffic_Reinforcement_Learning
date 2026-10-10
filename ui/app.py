"""The application: one window, one screen at a time.

``App`` owns the settings, the file locations, the theme and the current screen.  Every
screen is a ``Screen`` subclass in ``ui/screens``; the menu opens the others with
``app.go("name")`` and each has a Back button to return.  Like ``SimulationScreen`` the
whole thing draws on any pygame surface, so tests (and ``--screenshot``) need no real window.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pygame

from agents.q_learning import ModelError, QLearningAgent
from config.settings import Settings
from ui.components import Button, Fonts, draw_text
from ui.theme import Theme, get_theme
from ui.widgets import Dialog
from utils import paths as default_paths

log = logging.getLogger(__name__)

WINDOW_TITLE = "Smart Traffic Light Control"
DEFAULT_MODEL_NAME = "q_learning_model.json"
TOAST_SECONDS = 6.0
MIN_WINDOW = (640, 480)  # smaller windows cannot hold the screens; the size is raised to this
MAX_CONSECUTIVE_FAILURES = 3


@dataclass
class AppPaths:
    """Where the application reads and writes files (tests point these at a temporary folder)."""

    model_path: Path
    csv_dir: Path
    graph_dir: Path
    results_dir: Path
    settings_file: Path

    @classmethod
    def default(cls) -> AppPaths:
        return cls(default_paths.MODEL_DIR / DEFAULT_MODEL_NAME, default_paths.CSV_DIR,
                   default_paths.GRAPH_DIR, default_paths.RESULTS_DIR, default_paths.SETTINGS_FILE)


class Screen:
    """Base class: buttons, key shortcuts, a header, a hint line and confirmation dialogs."""

    name = "screen"
    heading = ""

    def __init__(self, app: App) -> None:
        self.app = app
        self.buttons: list[Button] = []
        self._keys: dict[int, Button] = {}
        self.dialog: Dialog | None = None
        self.hover: tuple[int, int] | None = None
        self._laid_out_for: tuple[int, int] | None = None

    # ---- helpers for subclasses ---------------------------------------------------------------

    @property
    def theme(self) -> Theme:
        return self.app.theme

    @property
    def fonts(self) -> Fonts:
        return self.app.fonts

    @property
    def s(self) -> float:
        return self.app.fonts.scale

    @property
    def size(self) -> tuple[int, int]:
        return self.app.size

    def add(self, label: str | Callable[[], str], key: int | None, hint: str, tooltip: str,
            action: Callable[[], None], enabled: Callable[[], bool] | None = None) -> Button:
        button = Button(label, hint, tooltip, action, enabled)
        self.buttons.append(button)
        if key is not None:
            self._keys[key] = button
        return button

    def ask(self, message: str, *options: tuple[str, Callable[[], None]]) -> None:
        """Show a question; the last option is also chosen by Esc."""
        def wrap(action: Callable[[], None]) -> Callable[[], None]:
            def run() -> None:
                self.dialog = None
                action()
            return run
        self.dialog = Dialog(message, [(label, wrap(action)) for label, action in options])
        self.dialog.layout(pygame.Rect(0, 0, *self.size), self.fonts)  # so clicks work before the next draw

    # ---- to override ------------------------------------------------------------------------------

    def on_enter(self) -> None:
        """Called once when the screen opens."""

    def close(self) -> None:
        """Called when the screen is left for any reason; stop anything still running."""

    def layout(self, size: tuple[int, int]) -> None:
        """Place the buttons for a window of this size."""

    def update(self, seconds: float) -> None:
        """Called every frame."""

    def draw_content(self, surface: pygame.Surface) -> None:
        """Draw everything except the header, buttons and dialog."""

    def on_key(self, event: pygame.event.Event) -> bool:
        """Extra keys; return True if handled."""
        return False

    def on_click(self, pos: tuple[int, int]) -> bool:
        """Clicks on things that are not buttons; return True if handled."""
        return False

    def request_leave(self, target: str) -> None:
        """Leave for ``target`` ("menu", another screen, or "quit"); screens may ask first."""
        if target == "quit":
            self.app.quit_requested = True
        else:
            self.app.go(target)

    def back(self) -> None:
        self.request_leave("menu")

    # ---- events ------------------------------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.dialog = None
            self.request_leave("quit")
        elif event.type == pygame.MOUSEMOTION:
            self.hover = event.pos
        elif self.dialog is not None:
            self._dialog_event(event)
        elif event.type == pygame.KEYDOWN:
            self._key(event)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._click(event.pos)

    def _dialog_event(self, event: pygame.event.Event) -> None:
        dialog = self.dialog
        assert dialog is not None
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            dialog.pick(len(dialog.buttons) - 1)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for index, button in enumerate(dialog.buttons):
                if button.contains(event.pos):
                    dialog.pick(index)
                    return

    def _key(self, event: pygame.event.Event) -> None:
        if self.on_key(event):
            return
        button = self._keys.get(event.key)
        if button is not None:
            button.click()
        elif event.key == pygame.K_ESCAPE:
            self.back()

    def _click(self, pos: tuple[int, int]) -> None:
        for button in self.buttons:
            if button.contains(pos):
                button.click()
                return
        self.on_click(pos)

    # ---- drawing -----------------------------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        if self._laid_out_for != self.size:
            self.layout(self.size)
            self._laid_out_for = self.size
        theme, fonts, s = self.theme, self.fonts, self.s
        surface.fill(theme.background)
        draw_text(surface, self.heading, fonts.title, theme.accent, (round(28 * s), round(18 * s)))
        pygame.draw.line(surface, theme.panel_border, (round(28 * s), round(60 * s)),
                         (self.size[0] - round(28 * s), round(60 * s)))
        self.draw_content(surface)
        hovered = None if self.dialog else next(
            (b for b in self.buttons if self.hover and b.contains(self.hover)), None)
        for button in self.buttons:
            button.draw(surface, fonts, theme, button is hovered)
        self._draw_footer(surface, hovered)
        if self.dialog is not None:
            self.dialog.draw(surface, pygame.Rect(0, 0, *self.size), theme, fonts, self.hover)

    def _draw_footer(self, surface: pygame.Surface, hovered: Button | None) -> None:
        theme, fonts, s = self.theme, self.fonts, self.s
        y = self.size[1] - round(14 * s)
        if self.app.toast:
            text, kind = self.app.toast
            color = theme.warning if kind == "warning" else theme.good
            draw_text(surface, text, fonts.body, color, (round(28 * s), y), "bottomleft")
        elif hovered is not None and hovered.tooltip:
            draw_text(surface, hovered.tooltip, fonts.small, theme.text_dim, (round(28 * s), y), "bottomleft")


class App:
    """Settings, files, theme and the current screen."""

    def __init__(self, settings: Settings, paths: AppPaths | None = None,
                 size: tuple[int, int] | None = None) -> None:
        self.settings = settings.validate()
        self.paths = paths or AppPaths.default()
        self.size = clamp_size(size or (settings.display.window_width, settings.display.window_height))
        self.theme = get_theme(settings.display.theme)
        self.fonts = Fonts(max(0.67, min(2.0, self.size[1] / 720)))
        self.screen: Screen | None = None
        self.quit_requested = False
        self.failures = 0  # consecutive frames that raised an unexpected error
        self.fatal_message = ""
        self.toast: tuple[str, str] | None = None
        self._toast_left = 0.0
        self._model_cache: tuple[tuple, QLearningAgent | None, str] | None = None

    # ---- navigation ---------------------------------------------------------------------------------------

    def go(self, name: str, **options) -> Screen:
        from ui.screens import SCREENS
        if name not in SCREENS:
            raise ValueError(f"Unknown screen '{name}'. Choose from: {', '.join(SCREENS)}.")
        old = self.screen
        if old is not None:
            self._safely(old.close, "closing a screen")
        screen = SCREENS[name](self, **options)
        self.screen = screen
        log.info("Screen: %s", name)
        screen.on_enter()
        return screen

    def notify(self, text: str, kind: str = "info") -> None:
        self.toast, self._toast_left = (text, kind), TOAST_SECONDS

    def apply_settings(self, settings: Settings) -> None:
        """Use new settings from now on (the theme changes at once)."""
        self.settings = settings.validate()
        self.theme = get_theme(settings.display.theme)
        self._model_cache = None

    def resize(self, size: tuple[int, int]) -> None:
        self.size = clamp_size(size)
        self.fonts = Fonts(max(0.67, min(2.0, self.size[1] / 720)))

    # ---- the model ---------------------------------------------------------------------------------------------

    def model_status(self) -> tuple[str, str]:
        """("none" | "ok" | "bad", one line of text) for the model file."""
        agent, message = self._load_model()
        if agent is not None:
            return "ok", message
        return ("none" if not self.paths.model_path.exists() else "bad"), message

    def load_agent(self) -> QLearningAgent | None:
        """A fresh copy of the trained agent (None if there is no usable model)."""
        agent, _ = self._load_model()
        if agent is None:
            return None
        return QLearningAgent.load(self.paths.model_path, self.settings.rl, seed=self.settings.traffic.seed)

    def _load_model(self) -> tuple[QLearningAgent | None, str]:
        path = self.paths.model_path
        try:
            stat = path.stat()
            key = (str(path), stat.st_mtime_ns, stat.st_size, self.settings.rl.medium_traffic,
                   self.settings.rl.high_traffic, self.settings.rl.decision_interval)
        except FileNotFoundError:
            return None, "No trained model yet - use \"Train the agent\" first."
        except OSError as exc:
            return None, f"The model file cannot be read ({exc.strerror or exc})."
        if self._model_cache is not None and self._model_cache[0] == key:
            return self._model_cache[1], self._model_cache[2]
        try:
            agent = QLearningAgent.load(path, self.settings.rl, seed=self.settings.traffic.seed)
        except ModelError as exc:
            result: tuple[QLearningAgent | None, str] = (None, f"The model cannot be used: {exc}")
            log.warning("Model not usable: %s", exc)
        else:
            result = (agent, f"Model: trained {agent.episodes_trained} episodes")
        self._model_cache = (key, *result)
        return result

    # ---- frame loop ------------------------------------------------------------------------------------------------

    def update(self, seconds: float) -> None:
        if self._toast_left > 0:
            self._toast_left -= seconds
            if self._toast_left <= 0:
                self.toast = None
        if self.screen is not None:
            self._guard(lambda: self.screen.update(seconds))

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.VIDEORESIZE:
            self.resize((event.w, event.h))
            return
        if self.screen is not None:
            self._guard(lambda: self.screen.handle_event(event))

    def draw(self, surface: pygame.Surface) -> None:
        if self.screen is not None:
            self._guard(lambda: self.screen.draw(surface))

    # ---- the safety net --------------------------------------------------------------------------------

    def _safely(self, action: Callable[[], None], what: str) -> None:
        try:
            action()
        except Exception:  # noqa: BLE001 - cleanup must never stop the program
            log.exception("Error while %s", what)

    def _guard(self, action: Callable[[], None]) -> None:
        """Run one step of the window; an unexpected error is logged and the user is returned to
        the menu with a message instead of the program crashing."""
        try:
            action()
        except Exception:  # noqa: BLE001 - last line of defence of the window
            self.failures += 1
            name = self.screen.name if self.screen else "?"
            log.exception("Unexpected error on screen %s", name)
            if self.failures > MAX_CONSECUTIVE_FAILURES:
                self.fatal_message = ("The application keeps failing and will close. "
                                      "Technical details are in logs/application.log.")
                self.quit_requested = True
                return
            self.notify("Something went wrong, so you were returned to the menu. "
                        "Details are in logs/application.log.", "warning")
            if self.screen is None or self.screen.name != "menu":
                self.go("menu")
        else:
            self.failures = 0


def clamp_size(size: tuple[int, int]) -> tuple[int, int]:
    """Window sizes below the minimum are raised to it."""
    return (max(MIN_WINDOW[0], int(size[0])), max(MIN_WINDOW[1], int(size[1])))


def run_app(settings: Settings, paths: AppPaths | None = None, start: str = "menu") -> None:
    """Open the window with the menu and run until the user quits."""
    pygame.display.init()
    pygame.font.init()
    try:
        display = settings.display
        screen = pygame.display.set_mode((display.window_width, display.window_height), pygame.RESIZABLE)
        pygame.display.set_caption(WINDOW_TITLE)
        app = App(settings, paths, size=screen.get_size())
        app.go(start)
        clock = pygame.time.Clock()
        log.info("Application window opened (%dx%d)", *screen.get_size())
        while not app.quit_requested:
            seconds = clock.tick(display.fps) / 1000.0
            for event in pygame.event.get():
                app.handle_event(event)
                if event.type == pygame.VIDEORESIZE:
                    if (event.w, event.h) != app.size:  # smaller than the minimum: make the window bigger again
                        pygame.display.set_mode(app.size, pygame.RESIZABLE)
                    screen = pygame.display.get_surface()
            app.update(min(seconds, 0.1))
            app.draw(screen)
            pygame.display.flip()
        log.info("Application window closed")
        if app.fatal_message:
            print(app.fatal_message, file=sys.stderr)
    finally:
        pygame.quit()


def render_screen(name: str, settings: Settings, paths: AppPaths | None = None,
                  size: tuple[int, int] | None = None, **options) -> pygame.Surface:
    """A picture of one screen, drawn off-screen (for screenshots and tests)."""
    pygame.font.init()
    app = App(settings, paths, size=size)
    app.go(name, **options)
    app.update(0.0)
    surface = pygame.Surface(app.size)
    app.draw(surface)
    return surface
