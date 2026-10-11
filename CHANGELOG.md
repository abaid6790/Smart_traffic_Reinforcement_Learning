# Changelog

All notable changes. Format follows [Keep a Changelog](https://keepachangelog.com/); versions follow
[Semantic Versioning](https://semver.org/). Dates are not recorded for early phases. Version numbers before 0.4.0 were not
written down at the time, so those phases are listed without one.

## [Unreleased]

Nothing yet. Contributors add their changes here ([CONTRIBUTING.md](CONTRIBUTING.md)).

## [1.0.0] - 2026-10-11 - Phase 11: final QA

### Added
* `docs/QA_CHECKLIST.md`: clean-environment install, end-to-end run, rule audit and the known limits.
* Documents for a complete project: `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/TEST_PLAN.md`, `docs/ROADMAP.md`,
  `docs/DISCLAIMER.md`, `docs/GLOSSARY.md`, `PRIVACY.md`, `COOKIE_POLICY.md`, `SECURITY.md`, `CONTRIBUTING.md`,
  `CODE_OF_CONDUCT.md`, `SUPPORT.md`, `THIRD_PARTY_NOTICES.md`, `CITATION.cff`, this changelog, and GitHub issue and pull
  request templates.
* `tests/test_policies.py`: tests that back the claims of the privacy, security and contributing documents.

### Fixed
* The documentation and syntax-guard tests scanned a virtual environment inside the project folder (any name other than
  `.venv`); they now scan only the project's own code.
* The logging comment claimed "no personal information is ever logged"; the log can contain file paths. Wording corrected.

## [0.8.0] - Phase 10: tests and documentation

### Added
* User guide, developer guide, RL explanation, project report, viva questions.
* `tests/test_documentation.py` (documentation checked against the code) and `tests/test_remaining_paths.py` (window
  loops, entry-point safety nets, missing optional libraries). Coverage 97 %.

### Fixed
* A model file that exists but cannot be read was shown as "no model yet"; it is now reported as unusable.
* The "3 failures in a row" safety net was reset by any successful step; failures now count per frame.
* Stale "to come" wording in documents and code comments.

## [0.7.0] - Phase 9: reliability

### Added
* Limits for time step, steps per run, settings file size (1 MB) and model file size (5 MB); minimum window 640 x 480.
* Safety net: an unexpected error in a screen is logged and returns to the menu.
* Delete buttons with confirmation for experiments, graphs and the model.
* `docs/RELIABILITY.md`, `tests/test_reliability.py` (23 tests).

### Fixed
* A tiny time step could make a run endless; deep or huge settings files and bad model fields raised unhandled errors; very
  small windows crashed drawing; a graph failure made finished training look failed; a stopped experiment left unequal run
  counts.

## [0.6.0] - Phase 8: menu and screens

### Added
* `python main.py --menu` with watch, compare side by side, train, experiment, results, settings and about screens;
  background jobs; settings form with validation.

### Fixed
* Python 3.11 compatibility in `evaluation/export.py` (nested quotes in an f-string); guard test added.

## [0.4.0] - Phase 7: evaluation

### Added
* Experiment runner: default fixed, tuned fixed and Q-Learning on identical seeds; mean with 95 % interval, paired verdicts;
  CSV, JSON, Markdown and graph export.

## Phases 1 to 6 (before 0.4.0)

* **Phase 1** foundation: validated settings, logging, safe paths, entry point.
* **Phase 2** headless simulation: vehicles, roads, traffic light with safety rules, seeded traffic.
* **Phase 3** fixed-time controller and metrics.
* **Phase 4** Pygame window.
* **Phase 5** RL environment: 18 states, KEEP/SWITCH, reward.
* **Phase 6** Q-Learning agent, training with best-policy selection, model files.
