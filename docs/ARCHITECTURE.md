# Architecture

How the parts fit together. For the code layout and extension recipes see [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md); for the
learning problem see [RL_EXPLAINED.md](RL_EXPLAINED.md).

## Layers

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Interface         main.py (command line)        ui/ (pygame window, screens)  │
├─────────────────────────────────────────────────────────────────────────────┤
│ Workflows         training/workflow.py   evaluation/experiment.py + export.py │
│                   ui/jobs.py (background thread)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│ Learning          agents/q_learning.py   training/trainer.py                  │
│                   environment/rl_env.py (state, actions, reward)              │
├─────────────────────────────────────────────────────────────────────────────┤
│ Control           controllers/ (fixed, tuned fixed, trained agent)            │
├─────────────────────────────────────────────────────────────────────────────┤
│ Simulation        simulation/ (simulator, runner, traffic generator)          │
│                   environment/ (vehicle, road, traffic light)                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ Foundation        config/settings.py (settings, scenarios, validation)        │
│                   utils/ (safe paths, logging)                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Dependency rule:** a layer uses only the layers below it. Everything below "Interface" has no pygame import, so the
simulation runs without a window and fast. The `ui` package imports pygame only when a window is opened.

## Main components

| Component | Responsibility |
|---|---|
| `Settings` | All parameters in six sections (simulation, lights, fixed, traffic, rl, display), validated on load and on change |
| `TrafficGenerator` | Seeded arrivals per road; one random stream per road so roads never influence each other; depends only on scenario, seed, clock |
| `Road`, `Vehicle` | Car following, stop line, queues, waiting time and stops; overflow waits outside the map |
| `TrafficLight` | State machine green, yellow, all-red; accepts **requests** only; enforces minimum and maximum green |
| `Simulator` | Advances time by `dt`; owns roads, light and generator; checks for crossing conflicts every step |
| `Controller` | Interface: `act(sim)` may request a switch. Implementations: fixed, tuned fixed, trained agent |
| `run_episode` | The single place where controller, simulator and metrics are combined, so every controller is run and measured the same way |
| `TrafficEnv` | The learning loop: `reset`, `step(action)` (one decision of 5 s plus any transition), state, reward |
| `QLearningAgent` | Q-table, epsilon-greedy choice, update rule, validated JSON model |
| `Trainer` | Episodes, validation every N episodes, best-policy selection, CSV log, pause and stop |
| `run_experiment` | All controllers on identical seeds; tuning; statistics; stop keeps only runs finished by every controller |
| `export` / `graphs` | CSV, JSON, Markdown and PNG output into a time-stamped folder |
| `App` and `Screen` | The window: screens, buttons with keys, dialogs, toasts, safety net |
| `BackgroundJob` | Runs training or an experiment in a thread with progress, pause, stop and friendly errors |

## One run

```
Settings ─► Simulator ─► [ controller.act(sim) ─► sim.step() ─► metrics ] × steps ─► EpisodeMetrics
```

## One learning step

```
state ─► agent.choose_action (epsilon-greedy)
      ─► env.step(action):  request switch? ─► simulate 5 s ─► (wait through yellow and all-red if switching)
      ─► reward, next state ─► agent.update(Q ← Q + α (r + γ max Q′ − Q))
```

The agent therefore only ever decides in steady-green states, and a switch costs its real transition time.

## One experiment

```
for each scenario:
    tune fixed greens on tuning seeds (base + 2,000,000 + k)
    for each run k (seed base + 1,000,000 + k):
        default fixed, tuned fixed, trained agent drive the same traffic
    statistics: mean, 95 % interval, paired differences, verdicts, checks (same traffic, 0 conflicts)
save: summary.md, runs.csv, summary.csv, comparison.csv, experiment.json, graphs/
```

## Threads

The window runs on the main thread. Training and experiments run in one `BackgroundJob` thread at a time. The job reports
progress through a lock-protected object that the screen reads each frame; pause and stop are events that the work checks
after each episode or run. Leaving a screen stops its job. The simulation itself is single-threaded and deterministic.

## Files and formats

| File | Format | Notes |
|---|---|---|
| Settings | JSON, six sections | Only changed values are needed; validated; written atomically; at most 1 MB when read |
| Model | JSON: `format`, `version`, `saved_at`, `training`, `parameters`, `state_design`, `q_table`, `visits` | `state_design` records thresholds and decision interval; a mismatch is refused; written atomically; at most 5 MB when read |
| Training log | CSV, one row per episode | |
| Experiment | `summary.md`, three CSV files, `experiment.json`, `graphs/*.png` | One time-stamped folder per experiment |
| Log | Text with rotation (1 MB, 3 backups) | May contain file paths ([PRIVACY.md](../PRIVACY.md)) |

## Error handling

1. **Validate early:** settings, model files and command-line values are checked at the edge and reported in plain English.
2. **Fail small:** a failure while saving graphs never loses the saved model or numbers.
3. **Safety net:** an unexpected error in a screen is logged and returns to the menu; the entry point has a last-resort
   handler and never prints a traceback. Details: [RELIABILITY.md](RELIABILITY.md).

## Design decisions

The reasons behind the main choices (simulation first, safety in the light, fairness by construction, small state, honest
baseline, three seed ranges, keep the best policy) are listed in [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md).
