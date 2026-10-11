# Security policy

## Scope and honest limits

This is an offline, single-user educational simulation. It has no network access, no accounts, no server and no database.
The realistic security concerns are:

1. **Untrusted files** that the program reads: a settings file, a model file, experiment result folders.
2. **Untrusted command-line values**, such as file names and paths.
3. **Deleting or overwriting the wrong files.**
4. **Dependencies** (`pygame`, `matplotlib` and what they install).

It is **not hardened for hostile multi-user systems** and has not had an independent security audit. **It must never be
connected to real traffic-control equipment** ([docs/DISCLAIMER.md](docs/DISCLAIMER.md)).

## Supported versions

| Version | Supported |
|---|---|
| 1.0.x | Yes |
| Older | No |

## Reporting a vulnerability

Please do **not** open a public issue for a security problem. Send a private report to _your security contact (e-mail or
private channel; replace this placeholder before publishing)_ with:

* what you found and why it matters,
* the version (`python main.py --version`) and your operating system,
* the steps or the file that reproduces it.

You can expect an acknowledgement within a reasonable time and a fix or an explanation afterwards. This is a student
project, so no service level or bounty is offered.

## What the program does to stay safe

| Concern | Protection | Checked by |
|---|---|---|
| Huge or malicious settings file | Rejected above 1 MB; invalid JSON, wrong types, extreme or non-finite numbers and deep nesting give a plain message, never a crash or hang | `tests/test_reliability.py` |
| Huge or malicious model file | Rejected above 5 MB; the structure, shapes, numbers and training information are validated before use | `tests/test_reliability.py` |
| Code execution from data | Models and settings are JSON. The code does not use `pickle`, `eval`, `exec`, `subprocess` or shell commands | `tests/test_policies.py` |
| Path tricks (`..`, absolute paths) | File names from users go through `safe_join`, which refuses to leave the intended folder | `tests/test_paths_and_logging.py` |
| Deleting the wrong thing | Only folders named `experiment_*` inside the results folder and `.png` graphs can be deleted from the window, each after a confirmation; nothing is deleted while training runs | `tests/test_reliability.py` |
| Losing a model or settings file on failure | Files are written to a temporary file and then renamed, so an interrupted save leaves the old file intact | `tests/test_q_learning.py` (model), `tests/test_policies.py` (settings) |
| Endless or runaway runs | Limits on time step, steps per run, episodes and runs | `tests/test_config.py`, `tests/test_reliability.py` |
| Network exposure | None: the code imports no networking library | `tests/test_policies.py` |
| Information leakage | Nothing is sent anywhere. The local log can contain file paths ([PRIVACY.md](PRIVACY.md)) | review |

## Advice for users

* Only open model or settings files from sources you trust, as you would with any file. They cannot run code, but a
  wrong model gives meaningless results.
* Keep dependencies current: `pip install --upgrade -r requirements.txt`. To check them for known issues you can use a tool
  such as `pip-audit` (not part of this project).
* Use a virtual environment (`python -m venv .venv`).
* Check `logs/application.log` before sharing it.

## Dependencies

Runtime dependencies are listed in `requirements.txt` and their licenses in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). The project does not bundle them; `pip` installs them from the Python
Package Index.
