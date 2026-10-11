# Contributing

Thank you for helping. This is an academic project, so contributions are welcome as long as they keep its main rule: **no
fake results and no half-working features**. Please also read the [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to help

* Report a bug or suggest an improvement (use the templates in `.github/ISSUE_TEMPLATE`).
* Improve the documentation: unclear sentences, mistakes, missing explanations.
* Add a test for behaviour that is not tested yet.
* Take an item from [docs/ROADMAP.md](docs/ROADMAP.md). Please open an issue first so the work is not duplicated.

For security problems do **not** open a public issue; follow [SECURITY.md](SECURITY.md).

## Set up

```powershell
git clone <your copy of the repository>
cd smart-traffic-rl
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m unittest discover -s tests -t .
```

On macOS or Linux use `source .venv/bin/activate`. The whole suite takes about 1.5 minutes (longer on some Windows
machines) and must end with `OK`. To check for unused imports and names run `python -m pyflakes .` (install with
`pip install pyflakes`).

Read the [developer guide](docs/DEVELOPER_GUIDE.md) first: it explains the layout and has recipes for adding a scenario,
controller, setting, metric or screen.

## Rules for changes

1. **Safety lives in the traffic light.** A controller may only request a switch. Never let any code bypass minimum green,
   maximum green, yellow or all-red.
2. **Fairness.** Traffic must depend only on scenario, seed and clock. Keep the three seed ranges (training, validation,
   evaluation) separate.
3. **Nothing hard-coded.** User-facing numbers are settings in `config/settings.py` with a documented range and a check that
   rejects bad values.
4. **Honest reporting.** Numbers in the documentation come from real runs. Do not round a bad result into a good one.
5. **Clear errors.** Say what is wrong and what is allowed, in plain English. No tracebacks for the user.
6. **No network, no telemetry, no pickle/eval/exec/subprocess.** `tests/test_policies.py` enforces this.
7. **Python 3.11 compatible.** For example, do not nest the same quote character inside an f-string
   (`tests/test_python_compat.py` checks it).
8. **Paths with `pathlib`.** No hard-coded absolute paths or backslashes.
9. **Tests.** Every change comes with tests that fail without it. Where possible, check a formula against a hand
   calculation, not against the code's own output.
10. **Docs stay true.** Changing behaviour means updating the documents that describe it.
    `tests/test_documentation.py` fails when a document names an option, setting, scenario or file that does not exist, or a
    wrong test count.

## Workflow

1. Open or pick an issue and say you are working on it.
2. Create a branch: `git checkout -b short-description`.
3. Make small, focused commits with clear messages ("Fix queue count when a road is full", not "update").
4. Run the full test suite and `pyflakes`. Both must be clean.
5. Update [CHANGELOG.md](CHANGELOG.md) under "Unreleased".
6. Open a pull request using the template. Describe what changed, why, and how you tested it.

## Style

* Type hints and short docstrings that explain *why*.
* Small functions and modules; plain Python for logic, with pygame only in the `ui` package's drawing code.
* Match the surrounding code. No reformatting of code you did not change.

## Changing the state or reward

This invalidates trained models and previous results. Update `_design()` in `agents/q_learning.py` so old models are
refused, update [docs/RL_ENVIRONMENT.md](docs/RL_ENVIRONMENT.md), retrain and re-run the experiments, and replace every
number in the documentation that came from the old results. A pull request that changes the agent without new results
will not be accepted.

## Licence

By contributing you agree that your contribution is released under the project's [MIT licence](LICENSE).
