"""Drawing helpers shared by the screens: progress bar, chart, table, dialog, text field."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import pygame

from ui.components import Button, Fonts, draw_text, wrap_text
from ui.theme import Color, Theme


def draw_progress(surface: pygame.Surface, rect: pygame.Rect, fraction: float, theme: Theme) -> None:
    pygame.draw.rect(surface, theme.button, rect, border_radius=rect.height // 2)
    fraction = max(0.0, min(1.0, fraction))
    if fraction > 0:
        fill = pygame.Rect(rect.x, rect.y, max(rect.height, round(rect.width * fraction)), rect.height)
        pygame.draw.rect(surface, theme.accent, fill, border_radius=rect.height // 2)
    pygame.draw.rect(surface, theme.panel_border, rect, width=1, border_radius=rect.height // 2)


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "--"
    seconds = int(round(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def draw_line_chart(
    surface: pygame.Surface,
    rect: pygame.Rect,
    series: Sequence[tuple[str, Color, Sequence[float | None]]],
    theme: Theme,
    fonts: Fonts,
    title: str,
    y_label: str,
    x_label: str = "Episode",
) -> None:
    """A simple line chart with a frame, title, axis labels and a legend."""
    pygame.draw.rect(surface, theme.panel, rect, border_radius=8)
    pygame.draw.rect(surface, theme.panel_border, rect, width=1, border_radius=8)
    draw_text(surface, title, fonts.strong, theme.text, (rect.x + 12, rect.y + 8))
    legend_x = rect.right - 12
    for label, color, _ in reversed(series):
        r = draw_text(surface, label, fonts.small, theme.text_dim, (legend_x, rect.y + 12), "topright")
        pygame.draw.line(surface, color, (r.x - 24, r.centery), (r.x - 6, r.centery), 3)
        legend_x = r.x - 34
    plot = pygame.Rect(rect.x + 62, rect.y + 40, rect.width - 78, rect.height - 78)
    pygame.draw.rect(surface, theme.panel_border, plot, width=1)
    clean = [[v for v in values if v is not None] for _, _, values in series]
    flat = [v for values in clean for v in values]
    longest = max((len(values) for _, _, values in series), default=0)
    if not flat or longest < 2:
        draw_text(surface, "Waiting for data...", fonts.body, theme.text_dim, plot.center, "center")
    else:
        low, high = min(flat), max(flat)
        if high - low < 1e-9:
            low, high = low - 1, high + 1
        pad = (high - low) * 0.08
        low, high = low - pad, high + pad
        for fraction in (0.0, 0.5, 1.0):
            y = plot.bottom - fraction * plot.height
            value = low + fraction * (high - low)
            draw_text(surface, f"{value:.1f}", fonts.small, theme.text_dim, (plot.x - 6, y), "midright")
            if 0 < fraction < 1:
                pygame.draw.line(surface, theme.button, (plot.x, y), (plot.right, y))
        for _, color, values in series:
            points = [(plot.x + i / (longest - 1) * plot.width,
                       plot.bottom - (v - low) / (high - low) * plot.height)
                      for i, v in enumerate(values) if v is not None]
            if len(points) >= 2:
                pygame.draw.lines(surface, color, False, points, 2)
            elif points:
                pygame.draw.circle(surface, color, points[0], 3)
        draw_text(surface, "1", fonts.small, theme.text_dim, (plot.x, plot.bottom + 4))
        draw_text(surface, str(longest), fonts.small, theme.text_dim, (plot.right, plot.bottom + 4), "topright")
    draw_text(surface, x_label, fonts.small, theme.text_dim, (plot.centerx, rect.bottom - 6), "midbottom")
    label = fonts.small.render(y_label, True, theme.text_dim)
    surface.blit(pygame.transform.rotate(label, 90), (rect.x + 8, plot.centery - label.get_width() // 2))


def draw_table(
    surface: pygame.Surface,
    rect: pygame.Rect,
    header: Sequence[str],
    rows: Sequence[Sequence[str]],
    theme: Theme,
    fonts: Fonts,
    first_width: float = 0.42,
) -> int:
    """Draw a table; the first column is wider.  Returns the y below the last row."""
    columns = len(header)
    first = round(rect.width * first_width)
    other = (rect.width - first) // max(1, columns - 1)
    xs = [rect.x] + [rect.x + first + i * other for i in range(columns - 1)]
    row_h = round(fonts.body.get_height() * 1.45)
    y = rect.y
    pygame.draw.rect(surface, theme.button, (rect.x, y, rect.width, row_h), border_radius=4)
    for x, text in zip(xs, header):
        draw_text(surface, text, fonts.get(22, bold=True), theme.text, (x + 8, y + row_h // 2), "midleft")
    y += row_h
    for index, row in enumerate(rows):
        if index % 2:
            pygame.draw.rect(surface, theme.panel, (rect.x, y, rect.width, row_h))
        for column, (x, text) in enumerate(zip(xs, row)):
            font = fonts.small if column == 0 else fonts.body
            while column == 0 and font.size(text)[0] > first - 12 and len(text) > 8:
                text = text[:-2]
            draw_text(surface, text, font, theme.text if column else theme.text_dim,
                      (x + 8, y + row_h // 2), "midleft")
        y += row_h
    pygame.draw.rect(surface, theme.panel_border, (rect.x, rect.y, rect.width, y - rect.y), width=1, border_radius=4)
    return y


class Dialog:
    """A question with a few answer buttons, drawn over the screen (Esc picks the last one)."""

    def __init__(self, message: str, options: Sequence[tuple[str, Callable[[], None]]]) -> None:
        self.message = message
        self.options = list(options)
        self.buttons = [Button(label, "", "", lambda a=action: a()) for label, action in options]

    def pick(self, index: int) -> None:
        self.buttons[index].click()

    def layout(self, area: pygame.Rect, fonts: Fonts) -> pygame.Rect:
        width = min(area.width - 40, round(560 * max(1.0, fonts.scale)))
        lines = wrap_text(fonts.body, self.message, width - 40)
        line_h = fonts.body.get_height() + 4
        height = 40 + len(lines) * line_h + 30 + round(46 * fonts.scale) + 24
        card = pygame.Rect(0, 0, width, height)
        card.center = area.center
        bw = (width - 40 - 12 * (len(self.buttons) - 1)) // len(self.buttons)
        bh = round(44 * fonts.scale)
        for i, button in enumerate(self.buttons):
            button.rect = pygame.Rect(card.x + 20 + i * (bw + 12), card.bottom - 20 - bh, bw, bh)
        return card

    def draw(self, surface: pygame.Surface, area: pygame.Rect, theme: Theme, fonts: Fonts,
             hover: tuple[int, int] | None) -> None:
        shade = pygame.Surface(area.size, pygame.SRCALPHA)
        shade.fill((0, 0, 0, 160))
        surface.blit(shade, area.topleft)
        card = self.layout(area, fonts)
        pygame.draw.rect(surface, theme.panel, card, border_radius=12)
        pygame.draw.rect(surface, theme.accent, card, width=2, border_radius=12)
        y = card.y + 24
        for line in wrap_text(fonts.body, self.message, card.width - 40):
            y = draw_text(surface, line, fonts.body, theme.text, (card.x + 20, y)).bottom + 4
        for button in self.buttons:
            button.draw(surface, fonts, theme, hover is not None and button.contains(hover))


class TextEntry:
    """Keyboard entry of a short number or text (digits, minus, dot and letters as allowed)."""

    def __init__(self, text: str = "", allowed: str = "0123456789.-", max_length: int = 12) -> None:
        self.text, self.allowed, self.max_length = text, allowed, max_length

    def key(self, event: pygame.event.Event) -> str | None:
        """Handle a key.  Returns "commit" on Enter, "cancel" on Esc, else None."""
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return "commit"
        if event.key == pygame.K_ESCAPE:
            return "cancel"
        if event.key == pygame.K_BACKSPACE:
            self.text = self.text[:-1]
        else:
            char = getattr(event, "unicode", "")
            if char and char in self.allowed and len(self.text) < self.max_length:
                self.text += char
        return None


class NumberBox:
    """A whole number with - and + buttons that can also be typed (click the number, then Enter)."""

    def __init__(self, label: str, value: int, low: int, high: int, step: int = 1) -> None:
        self.label, self.low, self.high, self.step = label, low, high, step
        self.value = value
        self.entry: TextEntry | None = None
        self.error = ""
        self.enabled = True
        self.rect = pygame.Rect(0, 0, 0, 0)

    def _parts(self) -> tuple[pygame.Rect, pygame.Rect, pygame.Rect]:
        r = self.rect
        side = r.height
        return (pygame.Rect(r.x, r.y, side, r.height), pygame.Rect(r.x + side, r.y, r.width - 2 * side, r.height),
                pygame.Rect(r.right - side, r.y, side, r.height))

    def set_value(self, value: int) -> None:
        self.value = max(self.low, min(self.high, value))
        self.error = ""

    def click(self, pos: tuple[int, int]) -> bool:
        if not self.enabled or not self.rect.collidepoint(pos):
            return False
        minus, middle, plus = self._parts()
        if minus.collidepoint(pos):
            self.commit()
            self.set_value(self.value - self.step)
        elif plus.collidepoint(pos):
            self.commit()
            self.set_value(self.value + self.step)
        elif middle.collidepoint(pos):
            self.entry = TextEntry(str(self.value), "0123456789", 7)
        return True

    @property
    def editing(self) -> bool:
        return self.entry is not None

    def key(self, event: pygame.event.Event) -> bool:
        """Feed a key while typing.  Returns True if the key was used."""
        if self.entry is None:
            return False
        result = self.entry.key(event)
        if result == "commit":
            self.commit()
        elif result == "cancel":
            self.entry = None
        return True

    def commit(self) -> None:
        if self.entry is None:
            return
        text, self.entry = self.entry.text, None
        if not text:
            self.error = f"{self.label}: type a whole number."
            return
        number = int(text)
        if not self.low <= number <= self.high:
            self.error = f"{self.label} must be between {self.low} and {self.high}."
            return
        self.value, self.error = number, ""

    def draw(self, surface: pygame.Surface, theme: Theme, fonts: Fonts, hover: tuple[int, int] | None) -> None:
        minus, middle, plus = self._parts()
        for rect, text in ((minus, "-"), (plus, "+")):
            hot = self.enabled and hover is not None and rect.collidepoint(hover)
            pygame.draw.rect(surface, theme.button_hover if hot else (theme.button if self.enabled else theme.button_disabled),
                             rect, border_radius=6)
            pygame.draw.rect(surface, theme.panel_border, rect, width=1, border_radius=6)
            draw_text(surface, text, fonts.strong, theme.button_text if self.enabled else theme.text_dim, rect.center, "center")
        pygame.draw.rect(surface, theme.panel, middle)
        pygame.draw.rect(surface, theme.accent if self.editing else theme.panel_border, middle, width=2 if self.editing else 1)
        shown = (self.entry.text + "|") if self.entry is not None else f"{self.value:,}".replace(",", " ")
        draw_text(surface, shown, fonts.strong, theme.text if self.enabled else theme.text_dim, middle.center, "center")
