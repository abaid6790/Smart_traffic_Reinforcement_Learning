"""Saves an experiment to files: CSV, JSON, a Markdown summary and (optionally) graphs.

Everything for one experiment goes into its own folder, named with the time it was run so
earlier experiments are never overwritten::

    results/experiment_20261007_153012_rush_hour/
        runs.csv          one row per controller, scenario and seed (every metric)
        summary.csv       mean, standard deviation and 95 % confidence interval per metric
        comparison.csv    improvements and paired comparisons
        experiment.json   all of the above plus settings, seeds, model and tuning details
        summary.md        a readable report
        graphs/*.png      the comparison graphs (if matplotlib is installed)
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from evaluation.experiment import (
    FIXED,
    LABELS,
    METRICS,
    RL,
    TUNED,
    Comparison,
    ExperimentResult,
    ScenarioResult,
)
from evaluation.formatting import format_number

#: (candidate, base) pairs that are compared, in display order.
COMPARISONS = ((RL, FIXED), (RL, TUNED), (TUNED, FIXED))

RUN_COLUMNS = ("scenario", "controller", "run", "seed", "duration", "vehicles_arrived",
               "vehicles_served", "vehicles_unserved", "average_waiting_time",
               "average_waiting_time_all", "max_waiting_time", "average_queue_length",
               "max_queue_length", "average_travel_time", "average_stops", "total_stops",
               "throughput_per_minute", "light_switches", "total_reward", "safety_violations")


def experiment_folder(root: Path, result: ExperimentResult) -> Path:
    """A new, timestamped folder name for ``result`` under ``root`` (not created yet)."""
    stamp = datetime.fromisoformat(result.created).strftime("%Y%m%d_%H%M%S")
    names = "_".join(s.scenario for s in result.scenarios[:3])
    if len(result.scenarios) > 3:
        names = f"{len(result.scenarios)}_scenarios"
    folder = root / f"experiment_{stamp}_{names}"
    counter = 2
    while folder.exists():  # two experiments in the same second
        folder = root / f"experiment_{stamp}_{names}_{counter}"
        counter += 1
    return folder


def _cell(value: Any) -> Any:
    return "" if value is None else value


def write_runs_csv(path: Path, result: ExperimentResult) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(RUN_COLUMNS)
        for scenario in result.scenarios:
            for key in scenario.controllers:
                for r in scenario.records[key]:
                    m = r.metrics
                    values = {**m.to_dict(), "controller": key, "run": r.run, "seed": r.seed,
                              "total_reward": r.total_reward}
                    writer.writerow([_cell(values.get(c)) for c in RUN_COLUMNS])


def write_summary_csv(path: Path, result: ExperimentResult) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("scenario", "controller", "metric", "unit", "n", "mean", "std",
                         "ci95_low", "ci95_high"))
        for scenario in result.scenarios:
            for key in scenario.controllers:
                for info in METRICS:
                    s = scenario.summary(key, info.name)
                    writer.writerow([scenario.scenario, key, info.name, info.unit, s.n,
                                     _cell(s.mean), _cell(s.std), _cell(s.ci_low), _cell(s.ci_high)])


def _comparisons(scenario: ScenarioResult) -> list[Comparison]:
    rows = []
    for candidate, base in COMPARISONS:
        if candidate in scenario.records and base in scenario.records:
            rows.extend(scenario.compare(candidate, base, info.name) for info in METRICS)
    return rows


def write_comparison_csv(path: Path, result: ExperimentResult) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("scenario", "candidate", "base", "metric", "base_mean", "candidate_mean",
                         "improvement_percent", "mean_difference", "difference_ci95_low",
                         "difference_ci95_high", "runs_candidate_better", "runs_candidate_worse",
                         "runs_tied", "verdict"))
        for scenario in result.scenarios:
            for c in _comparisons(scenario):
                d = c.paired.differences
                writer.writerow([scenario.scenario, c.candidate, c.base, c.metric,
                                 _cell(c.base_mean), _cell(c.candidate_mean),
                                 _cell(c.improvement_percent), _cell(d.mean), _cell(d.ci_low),
                                 _cell(d.ci_high), c.paired.candidate_better,
                                 c.paired.candidate_worse, c.paired.ties, c.paired.verdict])


def to_json_data(result: ExperimentResult) -> dict[str, Any]:
    """The whole experiment as plain dictionaries and lists."""
    scenarios = []
    for scenario in result.scenarios:
        scenarios.append({
            "scenario": scenario.scenario,
            "seeds": scenario.seeds,
            "traffic_identical_for_all_controllers": scenario.traffic_was_identical(),
            "safety_violations": scenario.safety_violations(),
            "tuning": None if scenario.tuning is None else {
                k: v for k, v in asdict(scenario.tuning).items() if k != "tried"},
            "summary": {key: {info.name: asdict(scenario.summary(key, info.name)) for info in METRICS}
                        for key in scenario.controllers},
            "comparisons": [{
                "candidate": c.candidate, "base": c.base, "metric": c.metric,
                "base_mean": c.base_mean, "candidate_mean": c.candidate_mean,
                "improvement_percent": c.improvement_percent,
                "paired": asdict(c.paired),
            } for c in _comparisons(scenario)],
            "runs": [{**r.metrics.to_dict(), "controller": key, "run": r.run,
                      "total_reward": r.total_reward}
                     for key in scenario.controllers for r in scenario.records[key]],
        })
    return {
        "program": "Smart Traffic Light Control Using Reinforcement Learning",
        "version": result.version, "created": result.created,
        "runs_per_scenario": result.runs, "base_seed": result.base_seed,
        "stopped_early": result.stopped_early, "seconds": round(result.seconds, 1),
        "controllers": {k: LABELS[k] for k in (FIXED, TUNED, RL)},
        "model": result.model, "settings": result.settings, "scenarios": scenarios,
    }


def _fmt(value: float | None, digits: int) -> str:
    return format_number(value, digits=digits)


def _verdict_text(c: Comparison, info) -> str:
    d = c.paired.differences
    if c.paired.n == 0:
        return "n/a"
    where = f"{c.paired.candidate_better}/{c.paired.n} runs better"
    return f"{c.paired.verdict} ({where})" if d.ci_low is not None else f"n/a ({where})"


def markdown_report(result: ExperimentResult) -> str:
    """A readable report of the experiment."""
    lines = ["# Experiment results", ""]
    lines.append(f"Created {result.created} by version {result.version}. "
                 f"{result.runs} runs per controller and scenario, base seed {result.base_seed}, "
                 f"{result.settings['simulation']['duration']:g} s of simulated traffic per run.")
    if result.stopped_early:
        lines.append("\n**The experiment was stopped early; some runs are missing.**")
    lines += ["", "All controllers drove the **same traffic** in every run (same seed, scenario "
              "and duration). Numbers are means with 95 % confidence intervals (Student's t); "
              "\"improvement\" is the change of the mean relative to the baseline, and the verdict "
              "is \"better\"/\"worse\" only when the 95 % interval of the seed-by-seed difference "
              "excludes zero. See docs/EXPERIMENTS.md.", ""]
    if result.model:
        m = result.model
        scenarios_text = ", ".join(m["trained_on"]) if m["trained_on"] else "unknown scenarios"
        best_text = "" if m["best_episode"] is None else f" (best policy from episode {m['best_episode']})"
        lines.append(f"Q-Learning model: trained {m['episodes_trained']} episodes on {scenarios_text}{best_text}.")
        lines.append("")
    for scenario in result.scenarios:
        lines += _scenario_markdown(scenario)
    lines += ["## Honest notes", "",
              "* The Q-Learning agent can only be as good as its training; a model trained on "
              "other scenarios than the one tested is being tested on traffic it has not seen.",
              "* *Total reward* is the training reward formula applied identically to every controller "
              "on a 5 s grid. It penalises light switches, so it can rank controllers differently from "
              "waiting time; waiting time and queue length are the measures to judge by.",
              "* The tuned fixed-time controller's green times were chosen on separate seeds, not on "
              "the seeds shown here.", ""]
    return "\n".join(lines)


def _scenario_markdown(scenario: ScenarioResult) -> list[str]:
    keys = scenario.controllers
    lines = [f"## Scenario: {scenario.scenario}", ""]
    if scenario.tuning is not None:
        t = scenario.tuning
        lines.append(f"Tuned fixed-time green times: NS {t.ns_green:g} s, EW {t.ew_green:g} s "
                     f"(default: NS {t.start_ns_green:g} s, EW {t.start_ew_green:g} s); "
                     f"chosen on {t.runs} separate tuning seeds.")
        lines.append("")
    lines.append("| Metric | " + " | ".join(LABELS[k] for k in keys) + " |")
    lines.append("|---|" + "---|" * len(keys))
    for info in METRICS:
        cells = []
        for k in keys:
            s = scenario.summary(k, info.name)
            half = s.half_width
            cells.append("n/a" if s.mean is None else
                         f"{_fmt(s.mean, info.digits)}" + (f" ± {_fmt(half, info.digits)}" if half is not None else ""))
        lines.append(f"| {info.label} ({info.unit}) | " + " | ".join(cells) + " |")
    lines.append("")
    for candidate, base in COMPARISONS:
        if candidate not in scenario.records or base not in scenario.records:
            continue
        lines += [f"**{LABELS[candidate]} compared with {LABELS[base]}** (positive improvement = better)", "",
                  "| Metric | Improvement | Verdict |", "|---|---|---|"]
        for info in METRICS:
            c = scenario.compare(candidate, base, info.name)
            pct = "n/a" if c.improvement_percent is None else f"{c.improvement_percent:+.1f} %"
            lines.append(f"| {info.label} | {pct} | {_verdict_text(c, info)} |")
        lines.append("")
    lines.append(f"Checks: traffic identical for all controllers: "
                 f"{'yes' if scenario.traffic_was_identical() else 'NO'}; "
                 f"safety conflicts in all runs: {scenario.safety_violations()}.")
    lines.append("")
    return lines


def save_experiment(result: ExperimentResult, root: Path, graphs: bool = True) -> Path:
    """Write every file of the experiment into a new timestamped folder; returns the folder."""
    folder = experiment_folder(Path(root), result)
    folder.mkdir(parents=True, exist_ok=False)
    write_runs_csv(folder / "runs.csv", result)
    write_summary_csv(folder / "summary.csv", result)
    write_comparison_csv(folder / "comparison.csv", result)
    (folder / "experiment.json").write_text(
        json.dumps(to_json_data(result), indent=2), encoding="utf-8")
    (folder / "summary.md").write_text(markdown_report(result), encoding="utf-8")
    if graphs:
        from evaluation.graphs import save_experiment_graphs  # needs matplotlib
        save_experiment_graphs(result, folder / "graphs")
    return folder

