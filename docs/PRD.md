# Product Requirements Document (PRD)

| | |
|---|---|
| Product | Smart Traffic Light Control Using Reinforcement Learning |
| Version | 1.0.0 |
| Status | Delivered (all 11 phases complete) |
| Owner | _your name_ |
| Date | 2026-10-11 |
| Related | [PROJECT_REPORT.md](PROJECT_REPORT.md), [ARCHITECTURE.md](ARCHITECTURE.md), [TEST_PLAN.md](TEST_PLAN.md), [ROADMAP.md](ROADMAP.md) |

This document says **what** the product must do and why. It was written after delivery from the requirements that drove
the build, and every requirement carries the evidence that it is met.

## 1. Purpose and background

A fixed-time traffic light gives each direction a preset green regardless of demand. The product is an offline
simulation and learning environment in which a reinforcement-learning agent learns to control one four-way
intersection, and in which its performance is compared honestly with fixed-time control.

It is an **academic semester project and teaching tool**. It is not, and must never be connected to, real traffic-control
equipment (see [DISCLAIMER.md](DISCLAIMER.md)).

## 2. Goals and non-goals

### Goals

| ID | Goal |
|---|---|
| G1 | A safe, repeatable simulation of a four-way intersection with a fixed-time baseline |
| G2 | A Q-Learning agent that can only request light changes, so it cannot break a safety rule |
| G3 | A fair, statistically sound comparison of agent and baselines, reported honestly |
| G4 | A usable application so a non-programmer can train, test, compare and read results |
| G5 | Everything configurable, validated and reproducible; nothing faked |
| G6 | Documentation and tests good enough for a supervisor to verify the claims |

### Non-goals

Real traffic control; real data, cameras or sensors; several intersections; turning movements; pedestrians; emergency
vehicles; deep reinforcement learning; networking, accounts or cloud features; mobile or web versions.

## 3. Users

| User | Needs | Main tasks |
|---|---|---|
| **Student / author** | Build, run, understand and defend the project | Train, run experiments, read results, answer questions in the viva |
| **Supervisor / examiner** | Verify that results are real and fairly obtained | Read the report, re-run experiments, inspect the code and tests |
| **Learner** | Understand reinforcement learning on a concrete example | Watch the agent, read [RL_EXPLAINED.md](RL_EXPLAINED.md), change settings |
| **Developer** | Extend the project | Add scenarios, controllers, metrics ([DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)) |

## 4. User stories

1. As a student I want to train the agent with one command so that I get a model without writing code.
2. As a student I want to watch the agent and the fixed timer on identical traffic so that I can see the difference.
3. As an examiner I want experiments with identical traffic, many runs and confidence intervals so that I can trust a verdict.
4. As a learner I want to change learning and traffic settings in a window with explanations so that I can experiment.
5. As any user I want a clear message instead of a crash when a file or a value is wrong.
6. As any user I want to be asked before anything is deleted or replaced.

## 5. Functional requirements

Status: **Met** = implemented and covered by automated tests (see [TEST_PLAN.md](TEST_PLAN.md)).

### Simulation

| ID | Requirement | Status |
|---|---|---|
| FR-1 | Simulate four approach roads with vehicles that accelerate, brake, keep a gap, stop on red and queue | Met |
| FR-2 | A light with two phases and green, yellow, all-red transitions; minimum and maximum green enforced; conflicting greens impossible | Met |
| FR-3 | Seeded traffic in seven scenarios (low, medium, high, rush hour, balanced, uneven, random); traffic independent of the light | Met |
| FR-4 | No vehicle is lost: arrivals to a full road wait outside and keep accumulating waiting time | Met |
| FR-5 | Check every step that conflicting traffic is never in the crossing; report violations | Met |

### Control and learning

| ID | Requirement | Status |
|---|---|---|
| FR-6 | A fixed-time controller with configurable green times | Met |
| FR-7 | A tuned fixed-time controller whose greens are found per scenario on separate seeds | Met |
| FR-8 | An RL environment with 18 states, KEEP/SWITCH actions and a documented reward; the agent only requests switches | Met |
| FR-9 | Tabular Q-Learning with epsilon-greedy exploration, configurable parameters, best-policy selection on validation traffic | Met |
| FR-10 | Train from the command line and the window; pause, resume, stop and save; CSV log and graphs | Met |
| FR-11 | Save and load the model as a validated JSON file; refuse damaged or mismatching files with a clear message | Met |

### Evaluation

| ID | Requirement | Status |
|---|---|---|
| FR-12 | Run all controllers on identical seeds; separate seed ranges for training, validation and evaluation | Met |
| FR-13 | Report waiting time (served and all vehicles), queue, throughput, travel time, stops, switches and reward | Met |
| FR-14 | Mean with 95 % confidence interval, paired comparison, and a verdict that says "no clear difference" unless the interval excludes zero | Met |
| FR-15 | Save each experiment in its own time-stamped folder: `summary.md`, three CSV files, JSON, graphs | Met |

### Application

| ID | Requirement | Status |
|---|---|---|
| FR-16 | Window to watch the simulation with play, pause, step, speed, restart, new traffic, statistics, help | Met |
| FR-17 | Menu with screens: watch fixed, watch agent, compare side by side, train, experiment, results, settings, about | Met |
| FR-18 | Every button works and says why when disabled; no placeholder features | Met |
| FR-19 | Settings screen and JSON file with validation; invalid values cannot be saved | Met |
| FR-20 | Long jobs run in the background; leaving a running job asks first; stopping keeps what is finished | Met |
| FR-21 | Delete experiments, graphs and the model from the window, with confirmation | Met |
| FR-22 | Every function also available from the command line (`python main.py --help`) | Met |

## 6. Non-functional requirements

| ID | Requirement | Target | Evidence |
|---|---|---|---|
| NFR-1 Reliability | Bad input, damaged files and unexpected errors never crash the program or lose saved data | no traceback shown | [RELIABILITY.md](RELIABILITY.md), 23 reliability tests |
| NFR-2 Reproducibility | Same seed gives the same traffic and the same fixed-time results | exact | tests; results re-checked against the final code |
| NFR-3 Fairness | All controllers see identical vehicles; no result judged on practice traffic | checked in every run | experiment "traffic identical" check |
| NFR-4 Portability | Windows (PowerShell), Linux, macOS; Python 3.11 or newer | pass | full suite on Python 3.11 and 3.13; 577 of 589 tests passed on the author's Windows machine before a test-scan bug was fixed |
| NFR-5 Offline | No network access | none | [PRIVACY.md](../PRIVACY.md); test that no network library is imported |
| NFR-6 Performance | A 600 s run is much faster than real time | 420 evaluation runs plus tuning in 85 s | experiment record |
| NFR-7 Usability | Plain-language messages; keyboard keys on every button; never colour alone | met | UI tests, screenshots |
| NFR-8 Security | Untrusted files are size-limited and validated; no code execution from data | see [SECURITY.md](../SECURITY.md) | tests and code search |
| NFR-9 Maintainability | Small modules, type hints, tests, documented extension points | 97 % line coverage | coverage run |
| NFR-10 Privacy | No personal data collected or transmitted | none | [PRIVACY.md](../PRIVACY.md) |

## 7. Success criteria and results

| Criterion | Result |
|---|---|
| All functional requirements met | Yes |
| Zero safety conflicts in every run | Yes (0 in all experiment and training runs) |
| Agent beats the default 30 s timer | Yes in 6 of 7 scenarios (+15 % to +37 % lower average waiting time); worse in low traffic (−17 %) |
| Agent beats a tuned timer | Only in rush hour (+3.8 %); no clear difference in four scenarios; worse in low and medium traffic |
| Automated tests pass | 589 of 589 at delivery |

The agent did **not** beat the tuned baseline in most conditions. This is reported as it is; the product's value is the
honest comparison, not a favourable number.

## 8. Constraints and assumptions

* Standard library plus `pygame` (window) and `matplotlib` (graphs); no other runtime dependencies chosen by the project.
* The model is a table of 18 × 2 numbers, so the state design is fixed for a trained model; changing it requires retraining.
* One intersection, straight traffic, simplified driver model.
* Assumes the user runs Python 3.11+ and can use a command line.

## 9. Risks

| Risk | Mitigation |
|---|---|
| Results flattered by a weak baseline | Tuned baseline on separate seeds; paired statistics |
| Agent judged on traffic it practised on | Three non-overlapping seed ranges |
| Unreliable results from few runs | 20 runs per scenario, confidence intervals |
| Crash on bad files | Validation, size limits, safety net, 23 reliability tests |
| Python version mismatch | Syntax guard test; suite run on 3.11 |
| Window not verified on a real display by the developer | Manual test list in [TEST_PLAN.md](TEST_PLAN.md) |

## 10. Milestones

The 11 phases in [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md): foundation, headless simulation, fixed controller and metrics,
visualisation, RL environment, Q-Learning and training, evaluation, menu and screens, reliability, tests and documentation,
final QA. All complete.

## 11. Out of scope for this version

See [ROADMAP.md](ROADMAP.md) for ideas such as elapsed-green information in the state, reward tuning, several trained models
and deep reinforcement learning. They are ideas, not commitments.
