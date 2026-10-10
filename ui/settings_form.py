"""The settings screen's logic.  Plain Python (no pygame), so it is fully tested.

The form shows the most useful settings as fields grouped into pages.  Every change
goes through the same validation as a settings file (``Settings.from_dict``), so the
window can never save a value the rest of the program would reject.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config.settings import MAX_SEED, SCENARIO_NAMES, SPEED_CHOICES, THEMES, ConfigError, Settings


@dataclass(frozen=True)
class Field:
    section: str
    name: str
    label: str
    kind: str  # "int", "float", "choice" or "bool"
    help: str
    low: float = 0.0  # stepping limits for numbers (the real rules are in Settings)
    high: float = 0.0
    step: float = 1.0
    choices: tuple = ()
    unit: str = ""

    @property
    def key(self) -> tuple[str, str]:
        return (self.section, self.name)


PAGES: dict[str, tuple[Field, ...]] = {
    "Traffic": (
        Field("traffic", "scenario", "Traffic scenario", "choice",
              "How busy each road is. The same scenario and seed always give the same traffic.",
              choices=SCENARIO_NAMES),
        Field("traffic", "seed", "Random seed", "int",
              "Starting point of the random traffic. Same seed = same cars.", 0, MAX_SEED, 1),
        Field("simulation", "duration", "Run length", "float",
              "How many simulated seconds one run lasts.", 60, 3600, 60, unit="s"),
    ),
    "Lights": (
        Field("lights", "min_green", "Minimum green", "float",
              "A request to switch is ignored before this time (safety rule).", 1, 120, 1, unit="s"),
        Field("lights", "max_green", "Maximum green", "float",
              "The light switches by itself after this time (safety rule).", 5, 300, 5, unit="s"),
        Field("lights", "yellow", "Yellow time", "float", "Length of the yellow signal.", 1, 15, 1, unit="s"),
        Field("lights", "all_red", "All-red time", "float",
              "Both roads red between phases, so the crossing can clear.", 0, 15, 1, unit="s"),
        Field("fixed", "ns_green", "Fixed-time: North/South green", "float",
              "Green time of the baseline controller. Must lie between minimum and maximum green.",
              5, 120, 5, unit="s"),
        Field("fixed", "ew_green", "Fixed-time: East/West green", "float",
              "Green time of the baseline controller. Must lie between minimum and maximum green.",
              5, 120, 5, unit="s"),
    ),
    "Learning": (
        Field("rl", "episodes", "Training episodes", "int",
              "How many simulated runs the agent practises on.", 10, 100000, 50),
        Field("rl", "learning_rate", "Learning rate", "float",
              "How strongly one experience changes what the agent knows (0-1).", 0.01, 1.0, 0.01),
        Field("rl", "discount_factor", "Discount factor", "float",
              "How much future reward counts compared with immediate reward (0-1).", 0.0, 0.99, 0.05),
        Field("rl", "epsilon_decay", "Exploration decay", "float",
              "Exploration shrinks by this factor after every episode.", 0.9, 1.0, 0.005),
        Field("rl", "switch_penalty", "Switch penalty", "float",
              "Reward lost for every light change; discourages flickering.", 0.0, 20.0, 0.5),
    ),
    "Display": (
        Field("display", "theme", "Theme", "choice", "Colour theme of the window.", choices=THEMES),
        Field("display", "simulation_speed", "Starting speed", "choice",
              "Speed when a simulation window opens (x real time).", choices=SPEED_CHOICES),
        Field("display", "drive_on", "Drive on the", "choice",
              "Which side vehicles keep to.", choices=("right", "left")),
        Field("display", "show_statistics", "Show statistics", "bool",
              "Show live statistics in the simulation window."),
    ),
}
ALL_FIELDS: tuple[Field, ...] = tuple(f for page in PAGES.values() for f in page)
FIELD_BY_KEY = {f.key: f for f in ALL_FIELDS}


def format_value(field: Field, value: object) -> str:
    if field.kind == "bool":
        return "On" if value else "Off"
    if field.kind == "choice":
        return f"{value:g}x" if isinstance(value, float) and field.name == "simulation_speed" else str(value)
    if isinstance(value, float):
        text = f"{value:g}"
    else:
        text = str(value)
    return f"{text} {field.unit}".strip()


class SettingsForm:
    """Editable copy of the settings, with validation and saving."""

    def __init__(self, settings: Settings) -> None:
        self._original = settings
        self.data = settings.to_dict()
        self.messages: dict[tuple[str, str], str] = {}  # per-field typing errors

    # ---- values ------------------------------------------------------------------------------

    def value(self, field: Field):
        return self.data[field.section][field.name]

    def text(self, field: Field) -> str:
        return format_value(field, self.value(field))

    def set_value(self, field: Field, value) -> None:
        self.data[field.section][field.name] = value
        self.messages.pop(field.key, None)

    def set_text(self, field: Field, text: str) -> bool:
        """Set a number typed by the user.  Returns False (and remembers why) if it is not a number."""
        text = text.strip().replace(",", ".")
        try:
            if field.kind == "int":
                number = float(text)
                if number != int(number):
                    raise ValueError
                self.set_value(field, int(number))
            elif field.kind == "float":
                self.set_value(field, float(text))
            else:
                raise ValueError
        except (ValueError, OverflowError):
            what = "a whole number" if field.kind == "int" else "a number"
            self.messages[field.key] = f"{field.label}: '{text}' is not {what}."
            return False
        return True

    def adjust(self, field: Field, direction: int) -> None:
        """Step a field up (+1) or down (-1); choices cycle, switches toggle."""
        current = self.value(field)
        if field.kind == "bool":
            self.set_value(field, not current)
        elif field.kind == "choice":
            index = field.choices.index(current) if current in field.choices else 0
            self.set_value(field, field.choices[(index + direction) % len(field.choices)])
        else:
            new = current + direction * field.step
            new = max(field.low, min(field.high, new))
            if field.kind == "int":
                new = int(round(new))
            else:
                new = round(new, 6)
            self.set_value(field, new)

    # ---- checking and saving ----------------------------------------------------------------------

    def problems(self) -> list[str]:
        """All problems with the current values (typing errors first, then the settings rules)."""
        found = list(self.messages.values())
        try:
            Settings.from_dict(self.data)
        except ConfigError as exc:
            found.extend(p for p in exc.problems if p not in found)
        return found

    def settings(self) -> Settings:
        """The validated settings (raises ConfigError with plain-English problems)."""
        if self.messages:
            raise ConfigError(list(self.messages.values()))
        return Settings.from_dict(self.data)

    @property
    def dirty(self) -> bool:
        return self.data != self._original.to_dict()

    def save(self, path: Path | str) -> Settings:
        """Validate, write the file and make the saved values the new starting point."""
        settings = self.settings()
        settings.save(path)
        self._original = settings
        return settings

    def revert(self) -> None:
        self.data = self._original.to_dict()
        self.messages.clear()

    def reset_to_defaults(self) -> None:
        self.data = Settings().to_dict()
        self.messages.clear()
