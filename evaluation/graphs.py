"""Graphs (PNG files), drawn with matplotlib.

matplotlib is only imported when a graph is drawn, so everything else works without it.
Every graph has a title, labelled axes with units, a legend whenever there is more than one
series, readable fonts, and the values written on the bars (so no number depends on colour
alone).  The three controller colours are the first three slots of a palette that was checked
for colour-blind separation; the green one is lighter than ideal on a light background, which
is why the values are always printed next to the marks.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from evaluation.experiment import FIXED, LABELS, RL, TUNED, ExperimentResult, ScenarioResult

if TYPE_CHECKING:
    from training.trainer import EpisodeStats

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
COLORS = {FIXED: "#2a78d6", TUNED: "#eb6834", RL: "#1baf7a"}
DPI = 150


def _pyplot():
    import matplotlib
    matplotlib.use("Agg")  # draw to files only; no window needed
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.size": 12, "axes.titlesize": 15, "axes.titleweight": "bold",
        "axes.labelsize": 12, "xtick.labelsize": 11, "ytick.labelsize": 11,
        "legend.fontsize": 11, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE, "text.color": TEXT, "axes.labelcolor": TEXT_SECONDARY,
        "xtick.color": TEXT_SECONDARY, "ytick.color": TEXT_SECONDARY,
        "axes.edgecolor": GRID, "axes.spines.top": False, "axes.spines.right": False,
    })
    return plt


def _finish(plt, fig, ax, path: Path, title: str, xlabel: str, ylabel: str,
            legend: bool, note: str | None = None) -> Path:
    ax.set_title(title, loc="left", pad=14)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    if legend:
        ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.16 if note else -0.12),
                  ncol=4)
    if note:
        fig.text(0.01, 0.01, note, fontsize=9.5, color=TEXT_SECONDARY, ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.03 if note else 0, 1, 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return path


def bar_comparison(result: ExperimentResult, metric: str, title: str, ylabel: str,
                   path: Path, digits: int = 1) -> Path:
    """Grouped bars: scenarios along the bottom, one bar per controller, 95 % CI whiskers."""
    plt = _pyplot()
    scenarios = result.scenarios
    keys = [k for k in (FIXED, TUNED, RL) if any(k in s.records for s in scenarios)]
    width = 0.8 / len(keys)
    fig, ax = plt.subplots(figsize=(max(8.5, 2.0 + 1.7 * len(scenarios) * len(keys) / 3), 5.8))
    top = 0.0
    for i, key in enumerate(keys):
        xs, means, errors = [], [], []
        for j, scenario in enumerate(scenarios):
            if key not in scenario.records:
                continue
            s = scenario.summary(key, metric)
            if s.mean is None:
                continue
            xs.append(j + (i - (len(keys) - 1) / 2) * width)
            means.append(s.mean)
            errors.append(s.half_width or 0.0)
        bars = ax.bar(xs, means, width * 0.92, color=COLORS[key], label=LABELS[key],
                      edgecolor=SURFACE, linewidth=2, zorder=2)
        ax.errorbar(xs, means, yerr=errors, fmt="none", ecolor=TEXT_SECONDARY, elinewidth=1.4,
                    capsize=3, zorder=3)
        for bar, mean, err in zip(bars, means, errors):
            ax.annotate(f"{mean:.{digits}f}", (bar.get_x() + bar.get_width() / 2, mean + err),
                        xytext=(0, 3), textcoords="offset points", ha="center", va="bottom",
                        fontsize=9.5, color=TEXT)
            top = max(top, mean + err)
    ax.set_xticks(range(len(scenarios)))
    ax.set_xticklabels([s.scenario.replace("_", " ") for s in scenarios])
    ax.set_ylim(0, top * 1.15 if top else 1)
    runs = result.runs
    return _finish(plt, fig, ax, path, title, "Traffic scenario", ylabel, True,
                   f"Mean of {runs} runs per bar on identical traffic; whiskers are 95% confidence intervals.")


def over_time(scenario: ScenarioResult, field_name: str, title: str, ylabel: str, path: Path) -> Path | None:
    """Lines of a time series averaged over the runs of each controller."""
    plt = _pyplot()
    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    drawn = False
    for key in scenario.controllers:
        series = scenario.series.get(key)
        if not series:
            continue
        values = getattr(series, field_name)
        points = [(t, v) for t, v in zip(series.times, values) if v is not None]
        if not points:
            continue
        ax.plot([p[0] for p in points], [p[1] for p in points], color=COLORS[key], linewidth=2,
                label=LABELS[key])
        drawn = True
    if not drawn:
        plt.close(fig)
        return None
    ax.set_ylim(bottom=0)
    return _finish(plt, fig, ax, path, f"{title} - {scenario.scenario.replace('_', ' ')}",
                   "Simulated time (s)", ylabel, True,
                   f"Average of {scenario.runs} runs on identical traffic.")


def save_experiment_graphs(result: ExperimentResult, folder: Path) -> list[Path]:
    """Draw all comparison graphs of an experiment into ``folder``; returns the files."""
    folder = Path(folder)
    files = [
        bar_comparison(result, "average_waiting_time_all",
                       "Average waiting time per vehicle (lower is better)",
                       "Average waiting time, all vehicles (s)", folder / "waiting_time_comparison.png"),
        bar_comparison(result, "average_queue_length",
                       "Average queue length (lower is better)",
                       "Average number of waiting vehicles", folder / "queue_length_comparison.png"),
        bar_comparison(result, "throughput_per_minute",
                       "Throughput (higher is better)",
                       "Vehicles served per minute", folder / "throughput_comparison.png"),
    ]
    for scenario in result.scenarios:
        for field_name, title, ylabel, suffix in (
            ("average_wait_so_far", "Waiting time over time",
             "Average wait of vehicles served so far (s)", "waiting_over_time"),
            ("vehicles_in_system", "Vehicles in the system over time",
             "Vehicles on the roads or waiting to enter", "vehicles_over_time"),
        ):
            path = over_time(scenario, field_name, title, ylabel, folder / f"{scenario.scenario}_{suffix}.png")
            if path is not None:
                files.append(path)
    return files


def _rolling(values: Sequence[float | None], window: int) -> list[float | None]:
    from training.trainer import rolling_mean
    return rolling_mean(values, window)


def _training_graph(stats: Sequence[EpisodeStats], attribute: str, title: str, ylabel: str,
                    path: Path) -> Path:
    plt = _pyplot()
    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    episodes = [s.episode for s in stats]
    values = [getattr(s, attribute) for s in stats]
    window = max(1, min(50, len(stats) // 10 or 1))
    points = [(e, v) for e, v in zip(episodes, values) if v is not None]
    ax.scatter([p[0] for p in points], [p[1] for p in points], s=10, color=COLORS[FIXED], alpha=0.35,
               linewidths=0, label="Each episode", zorder=2)
    smooth = _rolling(values, window)
    line = [(e, v) for e, v in zip(episodes, smooth) if v is not None]
    ax.plot([p[0] for p in line], [p[1] for p in line], color=COLORS[FIXED], linewidth=2.2,
            label=f"Average of the last {window} episodes", zorder=3)
    return _finish(plt, fig, ax, path, title, "Training episode", ylabel, True,
                   "Exploration is high at the start of training, so early episodes are noisy.")


def save_training_graphs(stats: Sequence[EpisodeStats], folder: Path, stamp: str) -> list[Path]:
    """Training reward and queue length per episode (needs at least 2 episodes)."""
    if len(stats) < 2:
        return []
    folder = Path(folder)
    return [
        _training_graph(stats, "total_reward", "Training reward per episode (higher is better)",
                        "Total reward of the episode (points)", folder / f"training_{stamp}_reward.png"),
        _training_graph(stats, "average_queue_length", "Training queue length per episode (lower is better)",
                        "Average queue length (vehicles)", folder / f"training_{stamp}_queue.png"),
    ]
