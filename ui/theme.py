"""Colour themes.  Plain Python (no pygame needed).

Colours are ``(red, green, blue)`` tuples.  Two themes are provided; the choice
comes from ``settings.display.theme``.  Colour is never the only way information
is shown: signals also carry the words RED / YELLOW / GREEN, and waiting vehicles
are listed in the legend.
"""

from __future__ import annotations

from dataclasses import dataclass

from config.settings import ConfigError, THEMES

Color = tuple[int, int, int]


@dataclass(frozen=True)
class Theme:
    name: str
    background: Color  # window background
    ground: Color  # area around the roads
    road: Color
    box: Color  # the crossing
    lane_marking: Color
    stop_line: Color
    panel: Color  # side panel background
    panel_border: Color
    text: Color
    text_dim: Color
    accent: Color  # highlights (the RL accent colour)
    button: Color
    button_hover: Color
    button_disabled: Color
    button_text: Color
    vehicle_moving: Color
    vehicle_waiting: Color
    vehicle_outline: Color
    windshield: Color
    signal_housing: Color
    red: Color
    yellow: Color
    green: Color
    lamp_off: Color
    good: Color
    warning: Color


DARK = Theme(
    name="dark",
    background=(24, 26, 30),
    ground=(34, 37, 42),
    road=(62, 65, 71),
    box=(72, 75, 82),
    lane_marking=(205, 208, 214),
    stop_line=(240, 240, 240),
    panel=(30, 33, 38),
    panel_border=(58, 63, 72),
    text=(232, 234, 238),
    text_dim=(150, 156, 166),
    accent=(64, 196, 232),
    button=(48, 54, 64),
    button_hover=(66, 76, 92),
    button_disabled=(38, 42, 49),
    button_text=(232, 234, 238),
    vehicle_moving=(86, 156, 235),
    vehicle_waiting=(244, 160, 56),
    vehicle_outline=(14, 16, 20),
    windshield=(20, 28, 44),
    signal_housing=(16, 17, 20),
    red=(236, 74, 66),
    yellow=(250, 204, 54),
    green=(70, 205, 110),
    lamp_off=(52, 54, 58),
    good=(70, 205, 110),
    warning=(244, 160, 56),
)

LIGHT = Theme(
    name="light",
    background=(238, 240, 244),
    ground=(214, 220, 214),
    road=(120, 124, 132),
    box=(132, 136, 144),
    lane_marking=(250, 250, 250),
    stop_line=(255, 255, 255),
    panel=(250, 251, 253),
    panel_border=(196, 202, 212),
    text=(24, 28, 36),
    text_dim=(88, 96, 110),
    accent=(0, 120, 168),
    button=(226, 230, 238),
    button_hover=(206, 214, 228),
    button_disabled=(238, 240, 244),
    button_text=(24, 28, 36),
    vehicle_moving=(30, 96, 190),
    vehicle_waiting=(224, 120, 10),
    vehicle_outline=(30, 34, 42),
    windshield=(196, 214, 238),
    signal_housing=(36, 38, 44),
    red=(214, 48, 40),
    yellow=(238, 182, 0),
    green=(30, 160, 80),
    lamp_off=(150, 152, 158),
    good=(30, 140, 70),
    warning=(200, 100, 0),
)

_THEMES = {theme.name: theme for theme in (DARK, LIGHT)}
assert set(_THEMES) == set(THEMES), "every theme named in the settings needs a palette"


def get_theme(name: str) -> Theme:
    """Return the theme called ``name`` (``dark`` or ``light``)."""
    try:
        return _THEMES[name]
    except KeyError:
        raise ConfigError(
            [f"Unknown theme '{name}'. Choose one of: {', '.join(THEMES)}."]
        ) from None


def blend(first: Color, second: Color, amount: float) -> Color:
    """Mix two colours: 0 gives ``first``, 1 gives ``second``."""
    amount = max(0.0, min(1.0, amount))
    return (
        round(first[0] + (second[0] - first[0]) * amount),
        round(first[1] + (second[1] - first[1]) * amount),
        round(first[2] + (second[2] - first[2]) * amount),
    )
