# Developer guide

For someone who wants to read, change or extend the code. To just run the project see [USER_GUIDE.md](USER_GUIDE.md).

## Principles the code follows

1. **Simulation first, graphics last.** `environment/`, `simulation/`, `controllers/`, `agents/`, `training/` and
   `evaluation/` never import pygame. A run takes a fraction of a second; the window only draws what the simulator
   already computed.
2. **Safety lives in the light.** A controller can only *request* a switch (`TrafficLight.request_switch()`); the light
   enforces minimum green, maximum green, yellow and all-red. No controller, including the agent, can bend this.
3. **Fair by construction.** Traffic depends only on scenario, seed and clock (one random stream per road), never on
   what the light does. All controllers run through the same `run_episode` function.
4. **Nothing hard-coded.** Every number is a setting in `config/settings.py` with a documented range, validated when
   loaded. Errors are collected and reported together in plain English (`ConfigError`).
5. **No fake results.** Everything in a report comes from a real run. Averages that cannot be computed are `None`
   (shown as `n/a`), never 0.
6. **Windows-friendly and offline.** Paths use `pathlib`; nothing touches the network.
7. **Python 3.11 compatible.** Do not nest the same quote character inside an f-string
   (`tests/test_python_compat.py` parses every file with the 3.11 grammar).

## Layout

```text
main.py                   command line; opens the window; every command-line option is handled here
config/settings.py        Settings dataclasses, scenarios, validation, load/save of the JSON file
environment/              Vehicle, Road, TrafficLight (state machine + safety), TrafficEnv (RL wrapper)
simulation/               traffic generator, Simulator, run_episode, text demos
controllers/              Controller interface, FixedTimeController, RLController, green-time tuning
agents/q_learning.py      QLearningAgent: table, epsilon-greedy, update rule, validated model file
training/                 Trainer (loop, CSV log, pause/stop, best policy) and workflow (whole job for the UI)
evaluation/               metrics, stats, seeds, experiment runner, export, graphs, formatting
ui/                       pygame application: App, Screen base class, screens/, widgets, jobs, scene drawing
utils/                    safe paths, logging setup
tests/                    unittest; run with: python -m unittest discover -s tests -t .
docs/                     this documentation
```

## How one run works

```
Settings ──► Simulator(settings) ──► reset(seed)
                │
   run_episode: while not sim.finished:
                    controller.act(sim)      # may call sim.light.request_switch()
                    sim.step()               # dt = 0.5 s: spawn, move vehicles, advance the light
                    collector.record(sim)    # metrics
                └─► EpisodeResult(metrics, time series, simulator)
```

* `Simulator.step()` generates arrivals (`TrafficGenerator`), moves vehicles on each `Road` (car following, stop line,
  yellow rule), advances the `TrafficLight`, and checks that no conflicting traffic is in the crossing.
* `TrafficEnv` wraps the same simulator for learning: `reset()`, `step(action)`, `get_state()`, `calculate_reward()`.
  One env step is one *decision* (default 5 s, plus the transition if a switch happens), so the agent only sees steady
  green states. See [RL_ENVIRONMENT.md](RL_ENVIRONMENT.md).
* `Trainer` plays many episodes against `TrafficEnv`, updates the `QLearningAgent`, checks the greedy policy every
  `rl.validation_every` episodes on separate seeds and keeps the best one. See [Q_LEARNING.md](Q_LEARNING.md).
* `RLController` runs a trained agent through `run_episode` with exploration off and learning off.
* `evaluation.experiment.run_experiment` runs fixed, tuned fixed and RL on identical seeds and returns an
  `ExperimentResult`; `evaluation.export.save_experiment` writes the files. See [EXPERIMENTS.md](EXPERIMENTS.md).

## Seed ranges

| Purpose | Seeds |
|---|---|
| Training episode *i* | `base + i` |
| Evaluation run *k* | `base + 1,000,000 + k` |
| Validation and tuning run *k* | `base + 2,000,000 + k` |

Defined in `evaluation/seeds.py`. They never overlap, so nothing is judged on traffic it practised or was tuned on.

## The user interface

* `ui/app.py`: `App` owns the settings, the file locations (`AppPaths`), theme, fonts, the current screen, toasts and a
  cache of the model status. `app.go("results")` builds a screen from the `SCREENS` table in `ui/screens/__init__.py`.
* `Screen` base class: buttons with hotkeys (`self.add(label, key, key_label, tooltip, action, enabled)`), confirm dialogs
  (`self.ask(...)`), `request_leave` / `back`, a hint footer, and `close()` called when the screen is left.
* Slow work (training, experiments) runs in `ui/jobs.BackgroundJob` (idle, running, paused, stopping, done, stopped,
  failed) so the window stays responsive. Friendly error text comes from one place (`_friendly`).
* Logic that needs no window lives in plain Python so it can be tested without pygame: `ui/jobs.py`,
  `ui/settings_form.py`, `ui/results_data.py`, `training/workflow.py`, `ui/geometry.py`, `ui/session.py`, `ui/snapshot.py`.
* Safety net: `App` catches an error inside a screen, logs it, shows a message and returns to the menu; after three
  failures in a row it closes with the reason. See [RELIABILITY.md](RELIABILITY.md).

## Recipes

### Add a traffic scenario

Add a `ScenarioProfile` to `SCENARIOS` in `config/settings.py` (rates are arrivals per second per road; optional
`variation_amplitude` / `variation_period`). It then appears in `--list-scenarios`, the `--scenario` choices, the
training and experiment screens and the settings. Add a test that the generated arrivals match the rates
(see `tests/test_traffic_generator.py`).

### Add a controller

Subclass `controllers.base.Controller`, set `name`, implement `act(sim)` (look at the simulator, optionally call
`sim.light.request_switch()`) and `reset()` if it has state. Run it with `run_episode(settings, MyController(), seed)`.
To include it in experiments add it to the controller keys, labels and runner in `evaluation/experiment.py`
(`FIXED`, `TUNED`, `RL`, `LABELS`), and to `COMPARISONS` in `evaluation/export.py`.

### Add a setting

1. Add a field with a default to the right dataclass in `config/settings.py` and a `_between(...)` or other check in that
   dataclass's `problems()` method. Without a check, bad input would be accepted.
2. If users should change it in the window, add a `Field(...)` to `PAGES` in `ui/settings_form.py`.
3. Add a test in `tests/test_config.py` for a valid value and for each way it can be invalid.
4. If it changes the meaning of a saved model (state design, decision interval), also add it to `_design()` in
   `agents/q_learning.py`, which is stored in and checked against the model file.

### Add a metric

Add the measurement to `EpisodeMetrics` / `MetricsCollector` in `evaluation/metrics.py` (and document the formula in
[METRICS.md](METRICS.md)), then a `MetricInfo` in `METRICS` in `evaluation/experiment.py` and the column in
`RUN_COLUMNS` in `evaluation/export.py`. Test the formula against a hand calculation.

### Change the state or reward

Edit `environment/rl_env.py` (`encode_state`, `calculate_reward`). The Q-table size follows `all_states()`. A change of
state design means old models are invalid: make `_design()` in `agents/q_learning.py` record whatever now defines a state, so
old models are refused rather than misread, update [RL_ENVIRONMENT.md](RL_ENVIRONMENT.md) and retrain before comparing anything.

### Add a screen

Create `ui/screens/<name>.py` with a `Screen` subclass, register it in `SCREENS` (and in `SCREEN_NAMES` in `main.py` if
it should be reachable with `--screen`), add a menu button, and add it to `tests/test_app_screens.py` (every screen is
clicked through and drawn at several sizes and in both themes).

## Tests

```powershell
python -m unittest discover -s tests -t .
python -m pyflakes .          # optional: unused imports and names
```

| Group | Files |
|---|---|
| Settings, paths, logging | `test_config`, `test_paths_and_logging` |
| Simulation | `test_vehicle`, `test_road`, `test_traffic_light`, `test_traffic_generator`, `test_simulator`, `test_runner` |
| Controllers and metrics | `test_fixed_controller`, `test_metrics` |
| RL | `test_rl_env`, `test_q_learning`, `test_trainer` |
| Evaluation | `test_stats`, `test_experiment`, `test_export` |
| Window and application | `test_ui_logic`, `test_ui_screen`, `test_phase8_logic`, `test_app_screens` |
| Command line | `test_main` |
| Reliability and conventions | `test_reliability`, `test_remaining_paths`, `test_policies`, `test_python_compat`, `test_documentation` |

Window tests run without a display (`SDL_VIDEODRIVER=dummy` is set by the tests) and are skipped if pygame is not
installed. A full run takes about 1.5 minutes.

What the tests check beyond examples: every simulation step is checked for red-light running, overlapping vehicles, conflicting
traffic and lost vehicles; formulas are compared with hand calculations; two controllers get identical traffic; a watched
run gives the same numbers as a headless one; saved files match the in-memory results.

`tests/test_documentation.py` keeps the documentation honest: every command-line option mentioned in the docs must exist in
`main.py`, every file or link a document points to must exist, and the settings and scenarios named in the guides must
exist in the code.

## Conventions

* Type hints and short docstrings that say *why*, not only *what*.
* Plain-English error messages that say what is wrong and what is allowed.
* Long-running code takes a `should_stop` callback or runs in a `BackgroundJob`, never blocks the window.
* Files are written atomically where loss would hurt (model file), and a failure never destroys earlier data.
* Pitfall: tests patch names such as `LOG_DIR` and `MODEL_DIR` in the `main` module, so keep those imported there.
