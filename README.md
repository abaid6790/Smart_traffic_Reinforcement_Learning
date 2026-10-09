# Smart Traffic Light Control Using Reinforcement Learning

An academic semester project: a simulated four-way intersection where a
reinforcement-learning agent (tabular Q-Learning) will learn to control the traffic
light and be compared against a traditional fixed-time controller.

> **Disclaimer:** this is an educational simulation. It must never be connected to
> real traffic-control equipment.

## Project status

The project is being built slowly, one tested phase at a time.

| Phase | What | Status |
|------:|------|--------|
| 1 | Project setup: validated settings, logging, safe paths, entry point | **Done** |
| 2 | Headless simulation: vehicles, roads, traffic light with safety rules, seeded traffic | **Done** |
| 3 | Fixed-time controller and performance metrics | **Done** |
| 4 | Pygame visualisation: watch the simulation, speed control, pause/step | **Done** |
| 5 | RL environment: 18 states, KEEP/SWITCH actions, reward, safety enforced by the light | **Done** |
| 6 | Q-Learning agent, training (CSV log, safe stop, best-policy selection), model save/load | **Done** |
| 7 | Experiments: fixed vs tuned fixed vs RL on identical seeds, statistics, graphs, CSV/JSON/Markdown export | **Done** |
| 8 | Menu and screens (training, testing, experiments, results, settings) | Next |
| 9-11 | Reliability pass, docs, final QA | Planned |

See [docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md) for what each phase delivers.
The simulation window exists (Phase 4); the menu and result screens come in Phase 8.

![The simulation window, dark theme](docs/images/window_dark.png)

![The simulation window, light theme](docs/images/window_light.png)

## Requirements

* Python 3.11 or newer (developed and tested on Python 3.13)
* `pygame` (2.5.2 or newer) for the window and `matplotlib` for the graphs. The simulation, metrics,
  `--demo`, training, experiments and the settings need only the standard library; without
  matplotlib only the PNG graphs are skipped.

## Running (Windows PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

On macOS/Linux use `source .venv/bin/activate` instead of the activate line.

### Useful commands

```powershell
python main.py                          # overview of this build
python main.py --window                 # watch the fixed-time controller in a window
python main.py --window --scenario rush_hour --speed 5 --paused
python main.py --screenshot docs\images\frame.png --screenshot-at 90   # save a picture, no window
python main.py --demo                   # fixed-time controller: run, print report + metrics
python main.py --demo --scenario rush_hour --duration 300 --seed 7
python main.py --demo --ns-green 20 --ew-green 40   # change the baseline's green times
python main.py --train --scenario rush_hour --episodes 300   # train the Q-Learning agent, save models\q_learning_model.json
python main.py --demo --controller rl --scenario rush_hour   # run the trained agent
python main.py --window --controller rl                      # watch the trained agent
python main.py --model-info                                  # what the model learned
python main.py --experiment --experiment-scenarios all --runs 20   # fixed vs tuned fixed vs RL, writes results\experiment_...
python main.py --experiment --no-rl                          # fixed-time controllers only (no model needed)
python main.py --env-demo --duration 300     # RL environment played by a random agent (no learning)
python main.py --list-scenarios         # show the traffic scenarios
python main.py --write-settings         # create config\user_settings.json to edit
python -m unittest discover -s tests -t .   # run the automated tests
```

The same `--seed` always produces exactly the same traffic.

## The simulation window

`python main.py --window` opens the intersection with cars, signals and a side panel
showing the controller, scenario, seed, clock, live statistics and buttons. Every button
has a keyboard key, and `H` shows them in the window.

| Key | Action |
|-----|--------|
| Space | pause / resume (Replay when the run has finished) |
| S or Right | run one step (pauses first) |
| + / - or Up / Down | faster / slower |
| 1 - 5 | speed 0.5x, 1x, 2x, 5x, 10x |
| R | restart the same traffic |
| N | new traffic (next seed) |
| T / D | hide-show statistics / debug information |
| H | help |
| Esc or Q | close help, then quit |

What you see is what the simulator computed, nothing is faked for the picture:

* Vehicles are **blue when moving and orange when waiting** at a stop line. A legend
  explains it, and every signal head also spells out RED, YELLOW or GREEN, so the
  display never relies on colour alone.
* Motion is smoothed between simulation steps, but the signals drawn are the ones the
  vehicles actually obeyed. Watching never changes the results: a watched run gives
  exactly the same metrics as a headless run (there is a test for it).
* When a run ends a results card shows the metrics; Replay or New traffic starts again.
* Display settings (`display` section): `theme` (dark/light), `window_width`/`height`,
  `fps`, `simulation_speed`, `drive_on` (`right` or `left`, mirrors the lanes),
  `view_range` (metres of road shown, 30-300), `show_statistics`, `show_debug`.

If pygame is missing, `--window` explains how to install it instead of crashing.

## The RL environment

`environment/rl_env.py` exposes the simulator as `reset()`, `step(action)`, `get_state()`
and `calculate_reward()`. The state is 18 values (NS traffic level x EW traffic level x
current phase), the actions are KEEP and SWITCH, and the reward is the fall in waiting
vehicles minus a switch penalty and an excess-queue penalty. The agent can only *request*
a switch, so it cannot break a safety rule. Exact definitions, thresholds and the reward
formula are in [docs/RL_ENVIRONMENT.md](docs/RL_ENVIRONMENT.md); all numbers can be changed
in the `rl` settings section. Nothing learns yet: `--env-demo` uses a random agent only
to show that full episodes run safely.

## The Q-Learning agent

`python main.py --train` plays many simulated episodes and learns a table of 18 states x
2 actions (the update rule, epsilon-greedy exploration and the model file are explained in
[docs/Q_LEARNING.md](docs/Q_LEARNING.md)). Training writes a per-episode CSV log, can be
stopped safely with Ctrl+C, never overwrites a model by accident, and keeps the *best*
policy it found (checked on separate validation traffic) rather than just the last one,
because the greedy policy of a table that is still learning swings between good and bad.
A trained model runs through exactly the same pipeline as the fixed-time controller
(`--demo/--window/--screenshot` with `--controller rl`), with exploration off.

Early sanity checks are in `docs/Q_LEARNING.md`.

## Experiments and results

`python main.py --experiment` runs the default fixed-time controller, a *tuned* fixed-time controller
and the trained agent on identical traffic (same seeds) and reports means with 95 % confidence
intervals and a paired seed-by-seed verdict. It writes `summary.md`, CSV files, JSON and graphs to
`results/experiment_<time>_<scenarios>/`. Method, seeds and files: [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md).

Real results (20 runs, 7 scenarios, average waiting time of all vehicles): the agent beats the default
30/30 timer by 15-37 % in six of seven scenarios, but a tuned fixed-time controller is about as good:
Q-Learning is clearly better only in rush hour (+3.8 %), no different in four scenarios and worse in low and
medium traffic. These are the real numbers, not adjusted ones.

![Average waiting time per scenario](docs/images/experiment_waiting_time.png)

## Changing settings (no code editing needed)

Run `python main.py --write-settings`, then edit `config/user_settings.json`. Every
setting is documented in `config/settings.py` and is validated when loaded: a typo, a
wrong type or an out-of-range value gives a plain-English list of everything that
needs fixing, instead of a crash. You only need to list the values you want to change.

Example `user_settings.json`:

```json
{
  "traffic":    { "scenario": "rush_hour", "seed": 7 },
  "simulation": { "duration": 300 },
  "lights":     { "min_green": 8, "max_green": 45 },
  "fixed":      { "ns_green": 25, "ew_green": 35 }
}
```

## How the simulation works

* **Roads:** four approach roads (north, south, east, west). Vehicles on a road drive
  towards the intersection, stop at the stop line on red and drive straight through.
* **Vehicles:** each driver has a slightly different top speed, accelerates and
  brakes smoothly, keeps a safe gap to the car in front, and tracks waiting time,
  travel time and number of stops.
* **Traffic light:** two phases (North/South, East/West). Every change goes
  green -> yellow -> all-red -> other phase. The light enforces a **minimum green**
  (early switch requests are ignored), a **maximum green** (it switches by itself) and
  makes conflicting greens impossible. Whoever controls the light, including the
  future RL agent, can only *request* a switch and cannot bypass these rules.
* **Yellow rule:** on yellow a vehicle stops if it comfortably can, and drives
  through only if it cannot stop in time. Settings are rejected if yellow + all-red is
  too short for vehicles to clear the crossing.
* **Traffic:** seven scenarios (low, medium, high, rush hour, balanced, uneven,
  random). Traffic depends only on the seed, scenario and clock, never on what the
  light does. This is what will make the fixed-vs-RL comparison fair.
* **No lost vehicles:** if a road is full, new arrivals wait outside the map and their
  waiting time still counts, so no controller can look better by losing cars.
* **Fixed-time controller (the baseline):** repeats NS green -> yellow -> all-red ->
  EW green -> yellow -> all-red with configurable green times (default 30 s each,
  yellow 5 s, all-red 2 s). It ignores traffic completely, like a plain timed signal.
  Green times must lie between the light's minimum and maximum green, otherwise the
  settings are rejected with an explanation.
* **Metrics:** waiting time, queue length, throughput, travel time and stops, plus
  percent-improvement formulas, all defined in [docs/METRICS.md](docs/METRICS.md).
  Two waiting-time averages are reported (served vehicles, and all vehicles including
  those still stuck), so a controller cannot look good just by leaving cars behind.
  Averages that cannot be computed show `n/a`, never a misleading 0.
* **Safety self-check:** every step the simulator checks that vehicles from both road
  pairs are never in the crossing box together; the demo reports the result.

## Project structure

```text
smart-traffic-rl/
├── main.py                     entry point / command line
├── config/settings.py          all settings, scenarios and validation
├── controllers/
│   ├── base.py                 the interface every controller follows
│   ├── fixed_controller.py     the fixed-time baseline
│   ├── rl_controller.py        runs a trained agent (epsilon 0)
│   └── tuning.py               finds the tuned fixed-time green times
├── agents/q_learning.py        Q-table, epsilon-greedy, update rule, model save/load
├── training/trainer.py         training loop, CSV log, pause/stop, best-policy selection
├── environment/
│   ├── enums.py                Direction, Phase, signal colours
│   ├── vehicle.py              one vehicle: motion, waiting time, stops
│   ├── road.py                 one approach road: queues, stop line, spacing
│   ├── traffic_light.py        light state machine and safety rules
│   └── rl_env.py               RL environment: state, actions, reward
├── simulation/
│   ├── traffic_generator.py    seeded vehicle arrivals per scenario
│   ├── simulator.py            roads + light + generator, step by step
│   ├── runner.py               one full episode: simulator + controller + metrics
│   ├── headless_demo.py        text report used by --demo
│   └── env_demo.py             random-agent demo used by --env-demo
├── ui/                         the window (pygame is imported only when used)
│   ├── theme.py  geometry.py   colours; road layout and drive side (plain Python)
│   ├── snapshot.py session.py  frozen states, interpolation; play/pause/speed logic
│   ├── components.py           fonts, text wrapping, buttons
│   ├── scene.py hud.py         drawing the intersection; side panel, help, results card
│   └── simulation_screen.py    events, buttons, window loop, screenshots
├── evaluation/
│   ├── metrics.py              metrics, time series, improvement formulas
│   ├── seeds.py  stats.py      separate seed ranges; mean, 95 % interval, paired comparison
│   ├── experiment.py           runs all controllers on identical seeds
│   ├── export.py  graphs.py    CSV / JSON / Markdown files; matplotlib graphs
│   └── formatting.py           metrics and experiments as readable text
├── utils/                      safe paths, logging
├── tests/                      automated tests (unittest)
├── docs/                       DEVELOPMENT_PLAN.md, METRICS.md, RL_ENVIRONMENT.md, Q_LEARNING.md, EXPERIMENTS.md, images/
├── models/  results/  logs/    created and used in later phases
└── LICENSE  requirements.txt  .gitignore
```

## Testing

```powershell
python -m unittest discover -s tests -t .
```

433 tests currently pass (the window tests run without a display). Besides unit tests of each class, the simulator tests run
whole simulations in every scenario, with and without aggressive light-switch
requests, and verify on every step that: no vehicle runs a red light, no vehicles
overlap, no conflicting traffic is in the crossing, no vehicle gets stuck, vehicles
are never created or lost, and identical seeds reproduce identical results.

Phase 3 tests check that the fixed controller's green, yellow and all-red times are
exact (also for other time steps), that metric formulas match hand-computed values,
that a hand-rolled measurement agrees with the collector, and that completely
different controllers face exactly the same vehicles (fair comparison).

Phase 4 tests cover the geometry (lanes on the correct side, opposite directions never
overlapping), snapshot interpolation, play/pause/speed timing, every key and button, the
drawing at several window sizes, themes and drive sides, screenshots, and that a signal
head lights only the colour it should.

Phase 5 tests check the 18-state encoding and thresholds, that the agent only ever sees
steady-green states, that refused switches are harmless, that an agent asking to switch at
every chance still obeys the minimum green and never causes a conflict, the reward formula
against hand calculation, determinism, and that the agent cannot change which vehicles arrive.

Phase 6 tests check the update rule against hand calculation, epsilon-greedy rates, model files
(round trip, atomic saving, every kind of damage, mismatched state design), training
(determinism, CSV log, stop/pause/resume, validation and best-policy selection, separate seed
ranges), and that a trained agent in `run_episode` makes exactly the decisions it made in the
training environment, for several decision intervals.

Phase 7 tests check the statistics against hand calculation, identical traffic across controllers, that tuning
uses separate seeds, the reward grid, file contents against the in-memory results, real PNG graphs, and the
command line (`--experiment` with and without a model, bad input).

The checks were themselves verified by deliberately injecting bugs (ignoring signals,
removing following distance, wrong green times, wrong averages, flipped improvement
sign, ...) and confirming the tests fail every time.

## Logging and privacy

Technical details are written to `logs/application.log`. Nothing is collected or sent
anywhere; the application works completely offline.

## Limitations (so far)

* In the real results a tuned fixed-time timer matches the agent in most scenarios (see above).
* One intersection, straight-through traffic only, simplified vehicle behaviour.
* Simulated traffic only; no real data, cameras, pedestrians or emergency vehicles.
* The window has been rendered and tested only off-screen (no real display) on Linux,
  so real-time smoothness on your machine is unchecked; try `--window` and tell me.
* Tested on Linux with Python 3.13; paths use `pathlib` so Windows is expected to
  work, but has not yet been run on a Windows machine.

## License

MIT, see [LICENSE](LICENSE). Replace the placeholder name in the license file with
your own.
