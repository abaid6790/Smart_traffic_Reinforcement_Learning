# Final QA (Phase 11)

What was checked on the final build, how, and what is **not** verified. Everything marked "checked" was run on the
delivered files, in a fresh folder with a fresh virtual environment created from `requirements.txt`
(Python 3.13, pygame 2.6.1, matplotlib 3.11).

## Clean-environment run

| Step | Result |
|---|---|
| `pip install -r requirements.txt` into a new venv | checked: installs and imports |
| `python main.py --version`, `--list-scenarios`, overview | checked |
| `--demo` with the fixed controller | checked: report printed, safety check PASSED |
| `--demo --controller rl` with no model | checked: friendly message, exit code 2, no traceback |
| `--train --train-scenarios all --episodes 200` | checked: model, CSV log and graphs written, 0 safety conflicts |
| `--model-info`, `--demo --controller rl` with the new model | checked |
| `--experiment` (low, rush hour, 5 runs, all three controllers) | checked: files and graphs written, traffic identical, 0 safety conflicts |
| `--env-demo` | checked |
| `--menu --screen X --screenshot` for all 7 screens, and the simulation window | checked: images produced and looked at |
| `--write-settings`, then a run that picks the file up | checked |
| A settings file with a wrong value | checked: plain message, exit code 2 |
| Full automated suite in the clean venv | checked: 578 tests OK |
| Full suite on Python 3.11 and 3.13 | checked: 578 tests OK on both |

## Project rules

| Rule | How it was checked | Result |
|---|---|---|
| No fake features or dead buttons | tests click every button of every screen and check its effect | pass |
| All results come from real runs | report numbers re-run with the final code (rush hour and low scenario identical); documentation tests compare quoted numbers across documents | pass |
| Fair comparison | same seeds for all controllers, checked by the program in every experiment ("traffic identical: yes"); separate seed ranges | pass |
| Settings validated | hostile-input tests (Phase 9); invalid values cannot be saved from the Settings screen | pass |
| Windows-friendly paths | no absolute paths, no `os.path`, no string-joined paths (searched); `pathlib` everywhere | pass (searched) |
| Offline | no network libraries imported anywhere (searched) | pass |
| Logging to `logs/application.log` | tests and the clean run | pass |
| No hard-coded user-facing numbers | every simulation, light, learning and display parameter is a validated setting. Remaining constants are internal tolerances (for example a 0.5 m stop tolerance), safety caps (maximum file sizes, maximum episodes and runs) and the seed-range offsets | pass, with those named exceptions |
| MIT license | `LICENSE` present | **you must replace the placeholder name** |
| Python 3.11 compatible | every file parsed with the 3.11 grammar; full suite run on 3.11 | pass |
| No leftovers | no TODO/FIXME, no bare `except`, no debug files; the delivered folder contains no logs, models, results or caches | pass |
| Documentation true | `tests/test_documentation.py` | pass |

## Known limits (not verified or not done)

* **Real display and Windows:** the window was rendered and tested off-screen on Linux only. Frame rate and feel on a
  real screen, and a full run on Windows, have not been verified by me. The code uses `pathlib` and a Python 3.11
  syntax guard because of this.
* **One trained model** is behind the reported results. Another training run could differ somewhat.
* **Best policy often comes from episode 20**, the first validation checkpoint (also in the 200-episode QA run), which
  suggests the 18-state design cannot learn much more (see `docs/Q_LEARNING.md`).
* **Mutation checks** (injecting bugs to see the tests fail) were done in Phases 2-8; they were not repeated for the Phase 9
  and 10 code.
* The results are for a simplified simulation (one intersection, straight traffic) and are not evidence about real roads.
