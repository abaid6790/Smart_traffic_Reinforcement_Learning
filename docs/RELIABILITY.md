# Reliability (Phase 9)

Goal: **bad input, damaged files and unexpected errors never crash the program, and never silently lose data.**
This phase was done by attacking the program (random and hostile input) and fixing what broke, not by assuming it was fine.

## What was tested

| Attack | How | Result |
|---|---|---|
| Settings file | Random, truncated, huge, deeply nested and wrong-type JSON; extreme numbers | Clear `ConfigError` message, never a crash or hang |
| Model file | Missing, empty, huge, wrong types, NaN/inf, bad table shape, bad training info | Clear message; buttons needing the model are disabled |
| Command line | 49 odd argument combinations | Friendly message, no traceback |
| File system | Read-only/missing folders, a file where a folder should be, deleted files | Friendly message; saved data is kept |
| Window | Random mouse/keyboard sessions on every screen, tiny and huge windows, errors injected into screens | App stays open; see "Safety net" |

## Bugs found and fixed

* `dt` of `1e-308` made a run effectively endless -> settings now have minimum/maximum limits (dt 0.01-1 s, acceleration and
  braking >= 0.1, and at most 2,000,000 steps per run).
* Deeply nested or enormous settings JSON raised an unhandled `RecursionError`/`ValueError` -> caught and reported; files over 1 MB are refused.
* Model files with bad `updates`, `final_epsilon` etc. raised `TypeError`/`ValueError` -> `training_info` is validated; model files over 5 MB are refused.
* A very small window crashed drawing -> minimum window size 640x480.
* A graph failure (matplotlib problem) made training or an experiment look failed after the data was saved -> the data stays, a note explains the graphs are missing.
* Stopping an experiment halfway left controllers with different run counts -> only runs finished by all controllers are kept.
* Raw file errors were shown to the user -> turned into plain sentences.

## Behaviour guarantees

* **Safety net:** an error inside a screen is logged to `logs/application.log`, a message is shown, and the app returns to the
  menu. Only after 3 failures in a row does it close, with the reason shown.
* **Confirmations:** deleting a model, a saved experiment or a training graph, replacing a model, resetting settings and leaving a
  running job all ask first. Nothing is deleted while training runs.
* **Delete safety:** only folders named `experiment_*` inside the results folder and `.png` graphs can be deleted; paths cannot escape the folder.
* **Closing a screen stops its background job**, so no work continues invisibly.
* **Nothing is overwritten by failure:** a training run that finishes no episode does not replace the existing model.

## Limits (all in `config/settings.py` and `agents/q_learning.py`)

`MAX_SETTINGS_FILE_BYTES` 1 MB, `MAX_MODEL_FILE_BYTES` 5 MB, `MAX_STEPS_PER_RUN` 2,000,000, `MIN_WINDOW` 640x480.

## Tests

`tests/test_reliability.py` (23 tests) keeps these behaviours from regressing.
