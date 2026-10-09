"""Small reusable pygame pieces: fonts, text and buttons."""

from __future__ import annotations

from collections.abc import Callable

import pygame

from ui.theme import Color, Theme

# Text anchors accepted by draw_text: which point of the text sits at ``pos``.
_ANCHORS = ("topleft", "topright", "midtop", "midleft", "center", "midright",
            "bottomleft", "midbottom", "bottomright")


class Fonts:
    """Fonts at a few sizes, created once.

    pygame's built-in font is used because it is bundled with pygame and so looks
    the same on every computer (system fonts differ between Windows, macOS, Linux).
    ``scale`` makes everything grow with the window height.
    """

    def __init__(self, scale: float = 1.0) -> None:
        pygame.font.init()
        self.scale = scale
        self._cache: dict[tuple[int, bool], pygame.font.Font] = {}

    def get(self, size: int, bold: bool = False) -> pygame.font.Font:
        """A font whose nominal size is ``size`` at scale 1 (never below 14)."""
        pixels = max(14, round(size * self.scale))
        key = (pixels, bold)
        if key not in self._cache:
            font = pygame.font.Font(None, pixels)
            font.set_bold(bold)
            self._cache[key] = font
        return self._cache[key]

    @property
    def title(self) -> pygame.font.Font:
        return self.get(34, bold=True)

    @property
    def big(self) -> pygame.font.Font:
        return self.get(46, bold=True)

    @property
    def body(self) -> pygame.font.Font:
        return self.get(26)

    @property
    def strong(self) -> pygame.font.Font:
        return self.get(26, bold=True)

    @property
    def small(self) -> pygame.font.Font:
        return self.get(21)


def draw_text(
    surface: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: Color,
    pos: tuple[float, float],
    anchor: str = "topleft",
) -> pygame.Rect:
    """Draw ``text`` so that its ``anchor`` point is at ``pos``; return its rectangle."""
    if anchor not in _ANCHORS:
        raise ValueError(f"Unknown text anchor {anchor!r}.")
    image = font.render(text, True, color)
    rect = image.get_rect(**{anchor: (round(pos[0]), round(pos[1]))})
    surface.blit(image, rect)
    return rect


def wrap_text(font: pygame.font.Font, text: str, max_width: int, max_lines: int = 99) -> list[str]:
    """Split ``text`` into lines no wider than ``max_width`` pixels.

    A word wider than the whole line is placed on a line of its own.  If the text needs
    more than ``max_lines`` lines, the last line ends with "...".
    """
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if current and font.size(trial)[0] > max_width:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and font.size(last + "...")[0] > max_width:
            last = last[:-1].rstrip()
        lines[-1] = last + "..."
    return lines


class Button:
    """A clickable button with a label, a keyboard hint and a tooltip.

    ``label`` and ``enabled`` may be functions, so a button can change as the program
    state changes (for example Pause / Play).
    """

    def __init__(
        self,
        label: str | Callable[[], str],
        hotkey: str,
        tooltip: str,
        action: Callable[[], None],
        enabled: Callable[[], bool] | None = None,
    ) -> None:
        self._label = label
        self.hotkey = hotkey
        self.tooltip = tooltip
        self._action = action
        self._enabled = enabled
        self.rect = pygame.Rect(0, 0, 0, 0)

    @property
    def label(self) -> str:
        return self._label() if callable(self._label) else self._label

    @property
    def enabled(self) -> bool:
        return self._enabled() if self._enabled is not None else True

    def contains(self, pos: tuple[int, int]) -> bool:
        return self.rect.collidepoint(pos)

    def click(self) -> bool:
        """Run the button's action if it is enabled.  Returns whether it ran."""
        if not self.enabled:
            return False
        self._action()
        return True

    def draw(self, surface: pygame.Surface, fonts: Fonts, theme: Theme, hovered: bool) -> None:
        enabled = self.enabled
        fill = theme.button_disabled if not enabled else (
            theme.button_hover if hovered else theme.button)
        border = theme.accent if hovered and enabled else theme.panel_border
        pygame.draw.rect(surface, fill, self.rect, border_radius=6)
        pygame.draw.rect(surface, border, self.rect, width=1, border_radius=6)
        text_color = theme.button_text if enabled else theme.text_dim
        draw_text(surface, self.label, fonts.get(24, bold=True), text_color,
                  (self.rect.centerx, self.rect.centery - 1), "center")
        if self.hotkey:
            draw_text(surface, self.hotkey, fonts.get(17), theme.text_dim,
                      (self.rect.right - 7, self.rect.bottom - 4), "bottomright")
