"""Finding and reading saved results for the results screen.  Plain Python.

Experiments are saved by ``evaluation.export.save_experiment`` as folders containing an
``experiment.json``.  This module lists those folders and turns the JSON into the few
numbers and sentences the screen shows.  A damaged or unfamiliar folder is reported, never
allowed to crash the screen.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from evaluation.experiment import FIXED, LABELS, METRIC_BY_NAME, RL, TUNED

log = logging.getLogger(__name__)

#: The metrics shown in the screen's table (the full set is in summary.md).
TABLE_METRICS = ("average_waiting_time_all", "average_queue_length", "max_queue_length",
                 "vehicles_served", "average_stops", "light_switches", "total_reward")


@dataclass(frozen=True)
class ExperimentInfo:
    path: Path
    name: str
    created: str = ""
    runs: int = 0
    scenarios: tuple[str, ...] = ()
    problem: str = ""  # set when the folder cannot be read

    @property
    def ok(self) -> bool:
        return not self.problem


def list_experiments(root: Path) -> list[ExperimentInfo]:
    """Experiment folders under ``root``, newest first (the folder name starts with the time)."""
    root = Path(root)
    if not root.is_dir():
        return []
    found = []
    for folder in sorted((p for p in root.iterdir() if p.is_dir() and p.name.startswith("experiment_")),
                         key=lambda p: p.name, reverse=True):
        try:
            data = read_experiment(folder)
        except ValueError as exc:
            found.append(ExperimentInfo(folder, folder.name, problem=str(exc)))
            continue
        found.append(ExperimentInfo(
            folder, folder.name, created=str(data.get("created", "")),
            runs=int(data.get("runs_per_scenario", 0) or 0),
            scenarios=tuple(s.get("scenario", "?") for s in data["scenarios"])))
    return found


def read_experiment(folder: Path) -> dict:
    """Load ``experiment.json``; ValueError with a friendly message if that is not possible."""
    path = Path(folder) / "experiment.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError("experiment.json is missing") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"experiment.json cannot be read ({exc})") from None
    except json.JSONDecodeError:
        raise ValueError("experiment.json is damaged (not valid JSON)") from None
    if not isinstance(data, dict) or not isinstance(data.get("scenarios"), list):
        raise ValueError("experiment.json does not look like experiment results")
    return data


@dataclass
class MetricRow:
    label: str
    cells: dict[str, str] = field(default_factory=dict)  # controller key -> "9.7 ± 0.5"


@dataclass
class ScenarioView:
    scenario: str
    controllers: list[str]
    rows: list[MetricRow]
    verdicts: list[str]  # sentences about the headline metric
    notes: list[str]


def _fmt(value, digits: int) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def scenario_names(data: dict) -> list[str]:
    return [s.get("scenario", "?") for s in data["scenarios"]]


def scenario_view(data: dict, scenario: str) -> ScenarioView:
    entry = next((s for s in data["scenarios"] if s.get("scenario") == scenario), None)
    if entry is None:
        raise ValueError(f"The results contain no scenario called {scenario}.")
    summary = entry.get("summary", {})
    controllers = [key for key in (FIXED, TUNED, RL) if key in summary]
    rows = []
    for name in TABLE_METRICS:
        info = METRIC_BY_NAME[name]
        row = MetricRow(f"{info.label} ({info.unit})")
        for key in controllers:
            cell = summary[key].get(name)
            if not cell or cell.get("mean") is None:
                row.cells[key] = "n/a"
                continue
            half = (cell["ci_high"] - cell["mean"]) if cell.get("ci_high") is not None else None
            row.cells[key] = (f"{_fmt(cell['mean'], info.digits)} ± {_fmt(half, info.digits)}"
                              if half is not None else _fmt(cell["mean"], info.digits))
        rows.append(row)
    verdicts = []
    for c in entry.get("comparisons", []):
        if c.get("metric") != "average_waiting_time_all":
            continue
        cand, base = LABELS.get(c["candidate"], c["candidate"]), LABELS.get(c["base"], c["base"])
        paired = c.get("paired", {})
        gain = c.get("improvement_percent")
        gain_text = "n/a" if gain is None else f"{gain:+.1f} %"
        verdicts.append(f"{cand} vs {base}: waiting time {gain_text} - {paired.get('verdict', 'n/a')} "
                        f"({paired.get('candidate_better', 0)}/{paired.get('n', 0)} runs better)")
    notes = []
    tuning = entry.get("tuning")
    if tuning:
        notes.append(f"Tuned fixed-time greens: NS {tuning['ns_green']:g} s, EW {tuning['ew_green']:g} s "
                     f"(default NS {tuning['start_ns_green']:g} s, EW {tuning['start_ew_green']:g} s).")
    notes.append("Same traffic for all controllers: "
                 + ("yes" if entry.get("traffic_identical_for_all_controllers") else "NO")
                 + f".  Safety conflicts: {entry.get('safety_violations', 0)}.")
    return ScenarioView(scenario, controllers, rows, verdicts, notes)


def list_graphs(folder: Path) -> list[Path]:
    """PNG graphs inside ``folder`` (or its ``graphs`` subfolder), sorted by name."""
    folder = Path(folder)
    for candidate in (folder / "graphs", folder):
        if candidate.is_dir():
            images = sorted(p for p in candidate.iterdir() if p.suffix.lower() == ".png")
            if images:
                return images
    return []
