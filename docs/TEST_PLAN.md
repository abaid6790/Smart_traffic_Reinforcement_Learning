# Test plan

## Strategy

Tests are layered so that a failure points to the cause. The simulation core is tested without any window, the window is
tested with a "dummy" video driver, and the documents are tested against the code.

```powershell
python -m unittest discover -s tests -t .      # everything; about 1.5 minutes (longer on some Windows machines)
python -m unittest tests.test_rl_env           # one file
python -m pyflakes .                           # unused imports and names (pip install pyflakes)
```

Status at delivery: **589 automated tests pass** on Python 3.13 and 3.11. A coverage run (Phase 10, before the last tests
were added) showed 97 % of the program's lines executed; most of the rest is code that only runs with a real display or
when a library is missing, which `tests/test_remaining_paths.py` then covered.

## What is tested, by area

| Area | Files | Examples of what is checked |
|---|---|---|
| Settings, paths, logging | `test_config`, `test_paths_and_logging` | every range and type, helpful messages, safe paths, log setup |
| Vehicles, roads, light | `test_vehicle`, `test_road`, `test_traffic_light` | gaps, stopping, queues, minimum and maximum green, yellow and all-red, no conflicting greens |
| Traffic | `test_traffic_generator` | same seed gives same cars, roads independent, rates match scenarios |
| Simulator and runner | `test_simulator`, `test_runner` | every step: no red-light running, no overlap, no conflicts, no lost vehicles, identical seeds identical results |
| Controllers, metrics | `test_fixed_controller`, `test_metrics` | exact green times, formulas against hand calculation |
| RL | `test_rl_env`, `test_q_learning`, `test_trainer` | 18 states, steady-green decisions, refused switches harmless, reward arithmetic, update rule, epsilon rates, model validation, determinism, best-policy selection, seed ranges |
| Evaluation | `test_stats`, `test_experiment`, `test_export` | t-intervals against hand values, paired verdicts, identical traffic across controllers, file contents equal in-memory results |
| Window | `test_ui_logic`, `test_ui_screen` | geometry, interpolation, timing, every key and button, drawing at several sizes, themes, drive sides |
| Application | `test_phase8_logic`, `test_app_screens` | every button of every screen, jobs, settings form, results, leaving asks first |
| Command line | `test_main` | each option, bad input, exit codes |
| Reliability | `test_reliability`, `test_remaining_paths` | hostile settings and model files, odd command lines, failing file systems, broken screens, window loops |
| Policies | `test_policies` | no network or code-execution calls, size limits, atomic settings save, documents match the limits |
| Conventions | `test_python_compat`, `test_documentation` | Python 3.11 syntax, documents match the code |

## Test quality measures

* **Hand calculations:** formulas (statistics, metrics, reward, update rule) are compared with values worked out by hand,
  not with the code's own output.
* **Bug injection:** during Phases 2 to 8, deliberate bugs (ignoring signals, removing the following distance, wrong green
  times, wrong averages, flipped improvement sign) were inserted to confirm the tests fail. This was **not repeated** for the
  Phase 9 to 11 code.
* **Fuzzing:** random and hostile settings, model files, command lines and window input were used in Phase 9 to find crashes
  (see [RELIABILITY.md](RELIABILITY.md)).
* **Coverage:** measured once with `coverage.py` (97 %).

## Acceptance tests (end to end)

Run on a clean virtual environment in Phase 11 ([QA_CHECKLIST.md](QA_CHECKLIST.md)): install, train, show the model,
run the agent, run an experiment, screenshot every screen, write and use a settings file, use a bad settings file.

## Manual tests on a real display

The window was only rendered off-screen during development. Please run these on your machine and note the result:

| # | Do | Expect |
|---|---|---|
| M1 | `python main.py --window` | Window opens; cars move smoothly; signals change green, yellow, red |
| M2 | Press Space, S, + and -, 1 to 5, R, N, H | Each does what the help says |
| M3 | Resize and maximise the window | Layout adapts; nothing overlaps; cannot shrink below 640 x 480 |
| M4 | `python main.py --menu`, press 1 to 8 | Each screen opens; Esc returns to the menu |
| M5 | Train 50 episodes from the window, Pause, Resume, Stop and save | Charts move; model saved; no freeze |
| M6 | Start training, press Back | Asks whether to stop; stopping saves the model |
| M7 | Compare side by side on rush hour | Both run on identical cars; summary text at the end |
| M8 | Run an experiment with 3 runs, then View results | Table and graphs shown |
| M9 | Settings: set an invalid value, Save | Plain explanation; not saved |
| M10 | Delete an experiment | Asks first; deleted only after confirming |
| M11 | Switch theme to light and Save | Colours change immediately |
| M12 | Move or rename the model file, open Train and Watch agent | Buttons disabled with an explanation; no crash |

## Not covered

Performance on slow computers, screen readers, very large monitors or unusual DPI settings, and long unattended runs
(many hours).

## Defect handling

A bug is fixed together with a test that fails without the fix, listed in [CHANGELOG.md](../CHANGELOG.md). Past defects
found by testing are in [RELIABILITY.md](RELIABILITY.md).
