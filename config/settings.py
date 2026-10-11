"""Central configuration for the Smart Traffic Light project.

Everything a user might reasonably want to tune lives here: road sizes, signal
timings, traffic scenarios, learning parameters and display options.  No other
module hard-codes these numbers; they receive a :class:`Settings` object (or
one of its sections) instead.

Settings can be changed in three ways:

* in code:     ``settings.with_changes("traffic", seed=7)``
* in a file:   ``python main.py --write-settings`` creates an editable JSON file
* in the UI:   the Settings screen of ``python main.py --menu`` (same validation)

Every value is validated.  All problems are collected and reported together in
one :class:`ConfigError`, so a user can fix everything in a single pass.

Units: metres (m), seconds (s) and metres per second (m/s), except where a
name says otherwise (``max_speed_kmh`` is km/h because it is friendlier to
edit).
"""

from __future__ import annotations

import json
import math
import types
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Union, get_args, get_origin, get_type_hints

PROJECT_NAME = "Smart Traffic Light Control Using Reinforcement Learning"
PROJECT_VERSION = "1.0.0"

DIRECTION_NAMES: tuple[str, ...] = ("north", "south", "east", "west")
PHASE_NAMES: tuple[str, ...] = ("NS", "EW")
SPEED_CHOICES: tuple[float, ...] = (0.5, 1.0, 2.0, 5.0, 10.0)
THEMES: tuple[str, ...] = ("dark", "light")
DRIVE_SIDES: tuple[str, ...] = ("right", "left")
MAX_SEED = 2**32 - 1
MAX_SETTINGS_FILE_BYTES = 1_000_000  # a real settings file is a few KB
MAX_STEPS_PER_RUN = 2_000_000  # one run may not need more simulation steps than this


class ConfigError(ValueError):
    """Raised when settings are missing, unreadable or invalid.

    ``problems`` holds one human-readable sentence per problem found.
    """

    def __init__(self, problems: list[str]) -> None:
        self.problems = list(problems)
        super().__init__("Invalid settings:\n - " + "\n - ".join(self.problems))


# --------------------------------------------------------------------------
# Traffic scenarios
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ScenarioProfile:
    """Describes how many vehicles arrive on each road.

    ``rates`` are average arrivals per second for each approach road.  When
    ``variation_amplitude`` is above zero the rate swings smoothly up and down
    over ``variation_period`` seconds (used by the "random" scenario).
    """

    name: str
    description: str
    rates: dict[str, float]
    variation_amplitude: float = 0.0
    variation_period: float = 120.0


def _even(rate: float) -> dict[str, float]:
    return {name: rate for name in DIRECTION_NAMES}


SCENARIOS: dict[str, ScenarioProfile] = {
    profile.name: profile
    for profile in (
        ScenarioProfile("low", "Light traffic on every road.", _even(0.04)),
        ScenarioProfile("medium", "Moderate traffic on every road.", _even(0.08)),
        ScenarioProfile("high", "Heavy traffic on every road.", _even(0.13)),
        ScenarioProfile(
            "rush_hour",
            "Very heavy traffic; roads can back up.",
            _even(0.20),
        ),
        ScenarioProfile(
            "balanced", "Similar traffic on all roads.", _even(0.10)
        ),
        ScenarioProfile(
            "uneven",
            "The north road is much busier than the others.",
            {"north": 0.20, "south": 0.08, "east": 0.06, "west": 0.06},
        ),
        ScenarioProfile(
            "random",
            "Traffic rises and falls continuously on every road.",
            _even(0.10),
            variation_amplitude=0.8,
            variation_period=150.0,
        ),
    )
}
SCENARIO_NAMES: tuple[str, ...] = tuple(SCENARIOS)


def get_scenario(name: str) -> ScenarioProfile:
    """Return the scenario called ``name`` or raise a friendly ConfigError."""
    try:
        return SCENARIOS[name]
    except KeyError:
        valid = ", ".join(SCENARIO_NAMES)
        raise ConfigError(
            [f"Unknown traffic scenario '{name}'. Choose one of: {valid}."]
        ) from None


# --------------------------------------------------------------------------
# Validation helpers
# --------------------------------------------------------------------------


def _fmt(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def _between(
    problems: list[str],
    label: str,
    value: float,
    low: float,
    high: float = math.inf,
    unit: str = "",
    *,
    low_exclusive: bool = False,
) -> None:
    """Record a problem unless ``low <= value <= high`` (NaN always fails)."""
    above = value > low if low_exclusive else value >= low
    if above and value <= high:
        return
    lower = f"greater than {_fmt(low)}" if low_exclusive else f"at least {_fmt(low)}"
    text = lower if high == math.inf else f"{lower} and at most {_fmt(high)}"
    problems.append(f"{label} must be {text}{unit} (got {value}).")


def _is_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


_INVALID = object()


def _convert(value: Any, hint: Any, label: str, problems: list[str]) -> Any:
    """Check ``value`` against a type hint; return it (converted) or _INVALID."""
    origin = get_origin(hint)
    if origin in (Union, types.UnionType):
        args = get_args(hint)
        if value is None and type(None) in args:
            return None
        options = [arg for arg in args if arg is not type(None)]
        return _convert(value, options[0], label, problems)
    if hint is bool:
        if isinstance(value, bool):
            return value
        problems.append(f"{label} must be true or false (got {value!r}).")
    elif hint is int:
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        problems.append(f"{label} must be a whole number (got {value!r}).")
    elif hint is float:
        if _is_number(value):
            return float(value)
        problems.append(f"{label} must be a number (got {value!r}).")
    elif hint is str:
        if isinstance(value, str):
            return value
        problems.append(f"{label} must be text (got {value!r}).")
    elif origin is dict:
        if isinstance(value, dict) and all(
            isinstance(k, str) and _is_number(v) for k, v in value.items()
        ):
            return {k: float(v) for k, v in value.items()}
        problems.append(
            f"{label} must be a list of name: number pairs (got {value!r})."
        )
    else:  # pragma: no cover - only reachable through a developer mistake
        problems.append(f"{label} has an unsupported type.")
    return _INVALID


# --------------------------------------------------------------------------
# Settings sections
# --------------------------------------------------------------------------


@dataclass
class SimulationConfig:
    """Physical size of the world and how vehicles move."""

    dt: float = 0.5  # simulation time step (s)
    duration: float = 600.0  # length of one run (s)
    road_length: float = 200.0  # approach road, spawn point to stop line (m)
    intersection_length: float = 12.0  # width of the crossing box (m)
    exit_length: float = 60.0  # road after the box, until vehicles vanish (m)
    vehicle_length: float = 4.5  # (m)
    min_gap: float = 2.0  # bumper-to-bumper gap when standing still (m)
    max_speed_kmh: float = 50.0  # speed limit (km/h)
    speed_variation: float = 0.15  # each driver's speed is limit * (1 +/- this)
    acceleration: float = 2.5  # (m/s^2)
    braking: float = 4.0  # comfortable braking (m/s^2)
    halting_speed: float = 0.5  # below this speed a vehicle counts as stopped (m/s)

    @property
    def max_speed_ms(self) -> float:
        """Speed limit in metres per second."""
        return self.max_speed_kmh / 3.6

    @property
    def clearance_time(self) -> float:
        """Minimum yellow + all-red time needed to empty the crossing box.

        Conservative: assumes a vehicle crosses at half the speed of the
        slowest driver.
        """
        slowest = 0.5 * self.max_speed_ms * (1.0 - self.speed_variation)
        return (self.intersection_length + self.vehicle_length) / slowest

    def problems(self) -> list[str]:
        found: list[str] = []
        _between(found, "simulation.dt", self.dt, 0.01, 1, " s")
        _between(found, "simulation.duration", self.duration, 0, 86_400, " s",
                 low_exclusive=True)
        _between(found, "simulation.road_length", self.road_length, 20, 2_000, " m")
        _between(found, "simulation.intersection_length",
                 self.intersection_length, 2, 100, " m")
        _between(found, "simulation.exit_length", self.exit_length, 10, 1_000, " m")
        _between(found, "simulation.vehicle_length", self.vehicle_length, 1, 20, " m")
        _between(found, "simulation.min_gap", self.min_gap, 0, 20, " m")
        _between(found, "simulation.max_speed_kmh", self.max_speed_kmh, 5, 150,
                 " km/h")
        _between(found, "simulation.speed_variation", self.speed_variation, 0, 0.5)
        _between(found, "simulation.acceleration", self.acceleration, 0.1, 10, " m/s^2")
        _between(found, "simulation.braking", self.braking, 0.1, 15, " m/s^2")
        _between(found, "simulation.halting_speed", self.halting_speed, 0.01, 5, " m/s")
        if not found:
            if self.duration < self.dt:
                found.append("simulation.duration must be at least one time step.")
            elif self.duration / self.dt > MAX_STEPS_PER_RUN:
                found.append(f"simulation.duration / simulation.dt is more than {MAX_STEPS_PER_RUN:,} steps; "
                             "use a shorter duration or a larger time step.")
            if self.road_length < 3 * (self.vehicle_length + self.min_gap):
                found.append(
                    "simulation.road_length is too short to hold a few vehicles."
                )
        return found


@dataclass
class TrafficLightConfig:
    """Signal timing and the safety limits the agent can never bypass."""

    min_green: float = 10.0  # a switch request is ignored before this (s)
    max_green: float = 60.0  # the light switches by itself after this (s)
    yellow: float = 5.0  # (s)
    all_red: float = 2.0  # both roads red between phases (s)
    initial_phase: str = "NS"  # "NS" or "EW"

    def problems(self) -> list[str]:
        found: list[str] = []
        _between(found, "lights.min_green", self.min_green, 0, 600, " s",
                 low_exclusive=True)
        _between(found, "lights.max_green", self.max_green, self.min_green, 600,
                 " s")
        _between(found, "lights.yellow", self.yellow, 0, 60, " s", low_exclusive=True)
        _between(found, "lights.all_red", self.all_red, 0, 60, " s")
        if self.initial_phase not in PHASE_NAMES:
            found.append(
                "lights.initial_phase must be 'NS' or 'EW' "
                f"(got {self.initial_phase!r})."
            )
        return found


@dataclass
class FixedTimeConfig:
    """Timing of the traditional fixed-time controller (the baseline).

    Yellow and all-red times come from the ``lights`` section.  Each green time
    must lie between ``lights.min_green`` and ``lights.max_green`` because the
    light itself enforces those limits.
    """

    ns_green: float = 30.0  # North/South green time (s)
    ew_green: float = 30.0  # East/West green time (s)

    def problems(self) -> list[str]:
        found: list[str] = []
        _between(found, "fixed.ns_green", self.ns_green, 0, 600, " s",
                 low_exclusive=True)
        _between(found, "fixed.ew_green", self.ew_green, 0, 600, " s",
                 low_exclusive=True)
        return found


@dataclass
class TrafficConfig:
    """Which traffic to generate.

    ``rate_scale`` multiplies every arrival rate (a simple "spawn rate" dial).
    ``direction_weights`` optionally re-distributes the scenario's total
    traffic between roads, e.g. ``{"north": 3, "south": 1, "east": 1, "west": 1}``.
    Roads that are not listed receive no traffic.
    """

    scenario: str = "balanced"
    seed: int = 42
    rate_scale: float = 1.0
    max_vehicles: int | None = None  # None = no limit
    direction_weights: dict[str, float] | None = None

    def problems(self) -> list[str]:
        found: list[str] = []
        if self.scenario not in SCENARIOS:
            found.append(
                f"traffic.scenario '{self.scenario}' is unknown. "
                f"Choose one of: {', '.join(SCENARIO_NAMES)}."
            )
        if not 0 <= self.seed <= MAX_SEED:
            found.append(
                f"traffic.seed must be a whole number from 0 to {MAX_SEED} "
                f"(got {self.seed})."
            )
        _between(found, "traffic.rate_scale", self.rate_scale, 0, 10,
                 low_exclusive=True)
        if self.max_vehicles is not None and self.max_vehicles < 1:
            found.append(
                "traffic.max_vehicles must be at least 1, or null for no limit "
                f"(got {self.max_vehicles})."
            )
        if self.direction_weights is not None:
            found.extend(self._weight_problems(self.direction_weights))
        return found

    @staticmethod
    def _weight_problems(weights: dict[str, float]) -> list[str]:
        found = []
        for name, weight in weights.items():
            if name not in DIRECTION_NAMES:
                found.append(
                    f"traffic.direction_weights has unknown road '{name}' "
                    f"(valid roads: {', '.join(DIRECTION_NAMES)})."
                )
            elif not weight >= 0:
                found.append(
                    f"traffic.direction_weights['{name}'] must be 0 or more "
                    f"(got {weight})."
                )
        if not found and not sum(weights.values()) > 0:
            found.append("traffic.direction_weights must contain a weight above 0.")
        return found


@dataclass
class RLConfig:
    """Q-Learning and RL-environment parameters."""

    learning_rate: float = 0.1
    discount_factor: float = 0.9
    epsilon: float = 1.0
    epsilon_decay: float = 0.995
    epsilon_min: float = 0.05
    episodes: int = 1000
    decision_interval: float = 5.0  # seconds between agent decisions
    # How busy a road pair is: vehicles approaching it that have not crossed the stop
    # line.  Below ``medium_traffic`` is Low, from there to below ``high_traffic`` is
    # Medium, and ``high_traffic`` or more is High.
    medium_traffic: int = 5
    high_traffic: int = 12
    # Reward = (waiting before - waiting after) - switch_penalty per light switch
    #          - queue_penalty per vehicle waiting beyond queue_limit.
    switch_penalty: float = 2.0
    queue_limit: int = 30
    queue_penalty: float = 0.2
    # While training, every ``validation_every`` episodes the agent's learned policy is
    # tried (without exploring) on ``validation_runs`` separate traffic runs, and the best
    # policy seen is kept.  0 turns this off.
    validation_every: int = 20
    validation_runs: int = 4

    def problems(self) -> list[str]:
        found: list[str] = []
        _between(found, "rl.learning_rate", self.learning_rate, 0, 1,
                 low_exclusive=True)
        _between(found, "rl.discount_factor", self.discount_factor, 0, 1)
        _between(found, "rl.epsilon", self.epsilon, 0, 1)
        _between(found, "rl.epsilon_decay", self.epsilon_decay, 0, 1,
                 low_exclusive=True)
        _between(found, "rl.epsilon_min", self.epsilon_min, 0, 1)
        _between(found, "rl.episodes", self.episodes, 1, 1_000_000)
        _between(found, "rl.decision_interval", self.decision_interval, 0, 60, " s",
                 low_exclusive=True)
        _between(found, "rl.medium_traffic", self.medium_traffic, 1, 1_000)
        _between(found, "rl.high_traffic", self.high_traffic, 2, 1_000)
        _between(found, "rl.switch_penalty", self.switch_penalty, 0, 1_000)
        _between(found, "rl.queue_limit", self.queue_limit, 0, 10_000)
        _between(found, "rl.queue_penalty", self.queue_penalty, 0, 1_000)
        _between(found, "rl.validation_every", self.validation_every, 0, 100_000)
        _between(found, "rl.validation_runs", self.validation_runs, 1, 100)
        if not found and self.high_traffic <= self.medium_traffic:
            found.append("rl.high_traffic must be larger than rl.medium_traffic.")
        if not found and self.epsilon_min > self.epsilon:
            found.append("rl.epsilon_min cannot be larger than rl.epsilon.")
        return found


@dataclass
class DisplayConfig:
    """Window and display options (used by the window and the menu)."""

    window_width: int = 1280
    window_height: int = 720
    fps: int = 60
    simulation_speed: float = 1.0
    theme: str = "dark"
    show_statistics: bool = True
    show_debug: bool = False
    drive_on: str = "right"  # which side vehicles keep to: "right" or "left"
    view_range: float = 60.0  # metres of each approach road shown on screen

    def problems(self) -> list[str]:
        found: list[str] = []
        _between(found, "display.window_width", self.window_width, 640, 7_680, " px")
        _between(found, "display.window_height", self.window_height, 480, 4_320,
                 " px")
        _between(found, "display.fps", self.fps, 10, 240)
        _between(found, "display.view_range", self.view_range, 30, 300, " m")
        if self.drive_on not in DRIVE_SIDES:
            found.append(
                f"display.drive_on must be one of {', '.join(DRIVE_SIDES)} "
                f"(got {self.drive_on!r})."
            )
        if self.simulation_speed not in SPEED_CHOICES:
            choices = ", ".join(f"{_fmt(s)}x" for s in SPEED_CHOICES)
            found.append(
                f"display.simulation_speed must be one of {choices} "
                f"(got {self.simulation_speed})."
            )
        if self.theme not in THEMES:
            found.append(f"display.theme must be one of {', '.join(THEMES)}.")
        return found


_SECTIONS: dict[str, type] = {
    "simulation": SimulationConfig,
    "lights": TrafficLightConfig,
    "fixed": FixedTimeConfig,
    "traffic": TrafficConfig,
    "rl": RLConfig,
    "display": DisplayConfig,
}


def _build_section(cls: type, raw: Any, name: str, problems: list[str]) -> Any:
    """Create one settings section from a dictionary, collecting problems."""
    if not isinstance(raw, dict):
        problems.append(f"Section '{name}' must be a group of name: value pairs.")
        return cls()
    hints = get_type_hints(cls)
    values: dict[str, Any] = {}
    for key, value in raw.items():
        if key not in hints:
            problems.append(f"Unknown setting '{name}.{key}'.")
            continue
        converted = _convert(value, hints[key], f"{name}.{key}", problems)
        if converted is not _INVALID:
            values[key] = converted
    return cls(**values)


@dataclass
class Settings:
    """All project settings, grouped into sections."""

    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    lights: TrafficLightConfig = field(default_factory=TrafficLightConfig)
    fixed: FixedTimeConfig = field(default_factory=FixedTimeConfig)
    traffic: TrafficConfig = field(default_factory=TrafficConfig)
    rl: RLConfig = field(default_factory=RLConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)

    # ---- validation ------------------------------------------------------

    def problems(self) -> list[str]:
        """Return every problem found (an empty list means the settings are OK)."""
        found: list[str] = []
        for name in _SECTIONS:
            found.extend(getattr(self, name).problems())
        if not found:
            needed = self.simulation.clearance_time
            have = self.lights.yellow + self.lights.all_red
            if have < needed:
                found.append(
                    f"lights.yellow + lights.all_red ({have:g} s) is too short for "
                    "vehicles to clear the intersection safely; it must be at "
                    f"least {needed:.1f} s."
                )
            low, high = self.lights.min_green, self.lights.max_green
            for label, value in (
                ("fixed.ns_green", self.fixed.ns_green),
                ("fixed.ew_green", self.fixed.ew_green),
            ):
                if not low <= value <= high:
                    found.append(
                        f"{label} ({value:g} s) must be between lights.min_green "
                        f"({low:g} s) and lights.max_green ({high:g} s). Change it, "
                        "or change the light limits."
                    )
        return found

    def validate(self) -> Settings:
        """Raise :class:`ConfigError` if anything is invalid; otherwise return self."""
        found = self.problems()
        if found:
            raise ConfigError(found)
        return self

    def updated(self, **sections: dict[str, Any]) -> Settings:
        """Return a validated copy with values changed in one or more sections.

        Changing several sections in one call matters when values depend on each
        other, for example ``lights`` limits and the ``fixed`` green times::

            settings.updated(lights={"max_green": 45}, fixed={"ns_green": 40})

        The changes pass through the same checks as a settings file: unknown
        names, wrong types and out-of-range values are all rejected.
        """
        data = self.to_dict()
        for name, changes in sections.items():
            if name not in _SECTIONS:
                raise ConfigError([f"Unknown settings section '{name}'."])
            if not isinstance(changes, dict):
                raise ConfigError(
                    [f"Changes to '{name}' must be a group of name: value pairs."]
                )
            data[name].update(changes)
        return Settings.from_dict(data)

    def with_changes(self, section: str, **changes: Any) -> Settings:
        """Return a validated copy with some values of one section changed."""
        return self.updated(**{section: changes})

    # ---- (de)serialisation ------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Plain dictionary of all settings (safe to store as JSON)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Any) -> Settings:
        """Build validated settings from a dictionary.

        Missing sections or values fall back to the defaults.  Unknown names
        and wrongly typed values are rejected so typos are not silently ignored.
        """
        if not isinstance(data, dict):
            raise ConfigError(["Settings must be a group of name: value pairs."])
        problems: list[str] = []
        sections: dict[str, Any] = {}
        for name, raw in data.items():
            if name not in _SECTIONS:
                valid = ", ".join(_SECTIONS)
                problems.append(f"Unknown settings section '{name}' (valid: {valid}).")
                continue
            sections[name] = _build_section(_SECTIONS[name], raw, name, problems)
        settings = cls(**sections)
        # Rejected values were replaced by defaults, so the range checks can still
        # run and report out-of-range values in the same pass.
        problems.extend(settings.problems())
        if problems:
            raise ConfigError(problems)
        return settings

    @classmethod
    def load(cls, path: Path | str) -> Settings:
        """Read and validate settings from a JSON file."""
        path = Path(path)
        try:
            if path.stat().st_size > MAX_SETTINGS_FILE_BYTES:
                raise ConfigError([f"Settings file {path} is larger than {MAX_SETTINGS_FILE_BYTES // 1024} KB; "
                                   "that is not a settings file."])
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise ConfigError([f"Settings file not found: {path}"]) from None
        except UnicodeDecodeError:
            raise ConfigError([f"Settings file {path} is not a UTF-8 text file."]) from None
        except OSError as exc:
            raise ConfigError(
                [f"Could not read settings file {path}: {exc.strerror or exc}"]
            ) from exc
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigError(
                [f"Settings file {path} is not valid JSON "
                 f"(line {exc.lineno}, column {exc.colno}): {exc.msg}."]
            ) from exc
        except (RecursionError, ValueError) as exc:  # absurdly deep nesting or huge numbers
            raise ConfigError([f"Settings file {path} cannot be read: it is too deeply nested "
                               "or contains an absurdly large number."]) from exc
        return cls.from_dict(data)

    def save(self, path: Path | str) -> None:
        """Validate and write settings to a JSON file (replaced atomically)."""
        self.validate()
        path = Path(path)
        temp = path.with_name(path.name + ".tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
            temp.replace(path)
        except OSError as exc:
            raise ConfigError(
                [f"Could not save settings to {path}: {exc.strerror or exc}"]
            ) from exc
