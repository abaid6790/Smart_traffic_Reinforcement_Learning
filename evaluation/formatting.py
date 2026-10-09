"""Turns metrics into readable text."""

from __future__ import annotations

from evaluation.experiment import FIXED, LABELS, RL, TUNED, ExperimentResult
from evaluation.metrics import EpisodeMetrics


def format_number(number: float | None, unit: str = "", digits: int = 1) -> str:
    """Format a number, showing ``n/a`` when it cannot be computed."""
    if number is None:
        return "n/a"
    return f"{number:.{digits}f}{unit}"


def format_metrics(metrics: EpisodeMetrics) -> list[str]:
    """Lines of a plain-text results table for one run."""
    safety = "PASSED" if metrics.safety_violations == 0 else "FAILED"
    return [
        f"Vehicles arrived          : {metrics.vehicles_arrived}",
        f"Vehicles served           : {metrics.vehicles_served}"
        f"  ({format_number(metrics.throughput_per_minute)} per minute)",
        f"Still in the system       : {metrics.vehicles_unserved}",
        f"Average waiting time      : {format_number(metrics.average_waiting_time, ' s')}"
        "  (served vehicles)",
        f"Average waiting time, all : {format_number(metrics.average_waiting_time_all, ' s')}"
        "  (including vehicles still waiting)",
        f"Maximum waiting time      : {format_number(metrics.max_waiting_time, ' s')}",
        f"Average queue length      : {format_number(metrics.average_queue_length)} vehicles",
        f"Maximum queue length      : {metrics.max_queue_length} vehicles",
        f"Average travel time       : {format_number(metrics.average_travel_time, ' s')}",
        f"Average stops per vehicle : {format_number(metrics.average_stops, digits=2)}",
        f"Light switches            : {metrics.light_switches}",
        f"Safety check (no crossing conflicts): {safety} "
        f"({metrics.safety_violations} conflicting steps)",
    ]


_SHOWN = ("average_waiting_time_all", "average_queue_length", "max_queue_length", "vehicles_served",
          "average_travel_time", "average_stops", "total_reward")


def format_experiment(result: ExperimentResult) -> list[str]:
    """Plain-text summary of an experiment for the console."""
    from evaluation.experiment import METRIC_BY_NAME

    lines: list[str] = []
    for scenario in result.scenarios:
        keys = scenario.controllers
        lines.append(f"Scenario {scenario.scenario}  ({scenario.runs} runs on identical traffic)")
        if scenario.tuning is not None:
            t = scenario.tuning
            lines.append(f"  tuned fixed-time greens: NS {t.ns_green:g} s, EW {t.ew_green:g} s "
                         f"(default NS {t.start_ns_green:g} s, EW {t.start_ew_green:g} s)")
        header = f"  {'metric':<46}" + "".join(f"{LABELS[k]:>24}" for k in keys)
        lines.append(header)
        for name in _SHOWN:
            info = METRIC_BY_NAME[name]
            cells = []
            for k in keys:
                s = scenario.summary(k, name)
                text = "n/a" if s.mean is None else f"{s.mean:.{info.digits}f}"
                if s.half_width is not None:
                    text += f" +/- {s.half_width:.{info.digits}f}"
                cells.append(f"{text:>24}")
            lines.append(f"  {info.label + ' (' + info.unit + ')':<46}" + "".join(cells))
        for candidate, base in ((RL, FIXED), (RL, TUNED), (TUNED, FIXED)):
            if candidate in scenario.records and base in scenario.records:
                c = scenario.compare(candidate, base, "average_waiting_time_all")
                q = scenario.compare(candidate, base, "average_queue_length")
                pct = "n/a" if c.improvement_percent is None else f"{c.improvement_percent:+.1f} %"
                qpct = "n/a" if q.improvement_percent is None else f"{q.improvement_percent:+.1f} %"
                lines.append(f"  {LABELS[candidate]} vs {LABELS[base]}: waiting time {pct} "
                             f"({c.paired.verdict}, better in {c.paired.candidate_better}/{c.paired.n} runs), "
                             f"queue {qpct} ({q.paired.verdict})")
        check = "same traffic for all controllers" if scenario.traffic_was_identical() else "TRAFFIC DIFFERED"
        lines.append(f"  checks: {check}; safety conflicts {scenario.safety_violations()}")
        lines.append("")
    return lines
