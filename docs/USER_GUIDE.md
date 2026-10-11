# User guide

This guide is for someone who wants to **run** the project: install it, watch the traffic light, train the
agent, run an experiment and read the results. You do not need to edit any code. For how the code is built, see
[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md); for the ideas behind it, [RL_EXPLAINED.md](RL_EXPLAINED.md).

> This is an educational simulation. It must never be connected to real traffic-control equipment.

## 1. Install

You need Python 3.11 or newer. In PowerShell, inside the project folder:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

`pygame` draws the window and `matplotlib` draws the graphs. If one of them is missing the program says so
and everything else still works (no window, or no PNG graphs). Nothing needs the internet after installation.

Check that everything works:

```powershell
python main.py            # prints an overview
python -m unittest discover -s tests -t .
```

## 2. The quickest tour (about 10 minutes)

```powershell
python main.py --menu
```

A menu opens. Every button has a number or letter shown in its corner, and hovering a disabled button explains why
it is disabled. Do these in order:

1. **Train the agent** (key `4`). Pick the traffic scenarios and the number of episodes (try `300` for a first
   look, `700` on all scenarios for the model used in the report). Press **Start training**. Watch the charts and
   the progress bar. You can **Pause**, or **Stop and save** at any time.
2. **Watch Q-Learning agent** (key `2`) shows the trained agent controlling the light. **Watch fixed-time light**
   (key `1`) shows the ordinary timer. Blue cars are moving, orange cars are waiting.
3. **Compare side by side** (key `3`) runs both on exactly the same cars. At the end it says how much lower or higher
   the agent's waiting time was. *One run proves nothing*; use an experiment for that.
4. **Run an experiment** (key `5`): choose scenarios and the number of runs (20 is the default). Press
   **Start experiment**, then **View results**.
5. **View results** (key `6`) shows saved experiments as a table with 95 % intervals and verdicts, or as graphs.

## 3. The screens

| Screen | Use it to | Notes |
|---|---|---|
| Watch fixed-time light / Watch Q-Learning agent | Watch one simulation | Keys: Space pause, S step, + / - speed, 1-5 preset speeds, R restart, N new traffic, T statistics, D debug, H help, Esc quit. The agent needs a trained model. |
| Compare side by side | Watch both controllers on identical traffic | Shows waiting time, queue, vehicles served and light switches live. |
| Train the agent | Create or improve the model | Never replaces a model without asking. *Continue the saved model* adds episodes to it. *Delete model* removes it (asks first, disabled while training). |
| Run an experiment | Compare all controllers statistically | Stop keeps only the runs that **every** controller finished, so the comparison stays fair. |
| View results | Read saved experiments and training graphs | Up/Down choose an item, Left/Right choose scenario or graph, T table, G graphs, Del deletes (asks first). |
| Settings | Change any number without editing files | Pages: Traffic, Lights, Learning, Display. Save, Revert, Defaults. |
| About | Reminder of what the program is and where files are | |

If the model is missing or damaged, only the buttons that need it are disabled; everything else works. Leaving a
screen while training or an experiment runs asks whether to stop it. Stopping saves what has been learned or
finished so far.

## 4. Settings

Open the **Settings** screen, or run `python main.py --write-settings` and edit `config/user_settings.json`. Either way
every value is checked, and a wrong value gives a plain explanation instead of a crash. You only need to list values
you want to change.

```json
{
  "traffic":    { "scenario": "rush_hour", "seed": 7 },
  "simulation": { "duration": 300 },
  "lights":     { "min_green": 8, "max_green": 45 },
  "fixed":      { "ns_green": 25, "ew_green": 35 }
}
```

The most useful settings:

| Setting | Default | Meaning |
|---|---|---|
| `traffic.scenario` | `balanced` | One of `low`, `medium`, `high`, `rush_hour`, `balanced`, `uneven`, `random` (`python main.py --list-scenarios`). |
| `traffic.seed` | 42 | The same seed always gives the same traffic. |
| `traffic.rate_scale` | 1.0 | Multiplies all arrival rates (0-10). |
| `simulation.duration` | 600 s | Length of one run. |
| `lights.min_green` / `max_green` | 10 s / 60 s | The light never switches before the minimum, and always switches after the maximum. |
| `lights.yellow` / `all_red` | 5 s / 2 s | Transition times. Too short to clear the crossing = rejected. |
| `fixed.ns_green` / `ew_green` | 30 s / 30 s | Green times of the fixed-time baseline. |
| `rl.learning_rate`, `discount_factor` | 0.1, 0.9 | Q-Learning parameters. |
| `rl.epsilon`, `epsilon_decay`, `epsilon_min` | 1.0, 0.995, 0.05 | Exploration schedule. |
| `rl.episodes` | 1000 | Default number of training episodes. |
| `rl.switch_penalty`, `queue_penalty`, `queue_limit` | 2.0, 0.2, 30 | Parts of the reward. |
| `display.theme` | `dark` | `dark` or `light`. |
| `display.drive_on` | `right` | `right` or `left` (mirrors the lanes). |

All settings and their allowed ranges are listed in `config/settings.py` and in the Settings screen. A model is bound to
the traffic thresholds and decision interval it was trained with; if you change those, the old model is refused and you
need to train again.

## 5. Command line

Everything in the application is also available from the command line (useful for long runs and scripts):

```powershell
python main.py --train --train-scenarios all --episodes 700
python main.py --model-info
python main.py --demo --controller rl --scenario rush_hour --seed 7
python main.py --experiment --experiment-scenarios all --runs 20
python main.py --experiment --no-rl                  # fixed-time controllers only
python main.py --window --scenario rush_hour --speed 5
python main.py --help                                # every option
```

Ctrl+C during `--train` stops safely and still saves the model.

## 6. Where files go

| What | Where |
|---|---|
| Trained model | `models/q_learning_model.json` |
| Training log (one row per episode) | `results/csv/training_<time>.csv` |
| Training graphs | `results/graphs/` |
| Experiments | `results/experiment_<time>_<scenarios>/` with `summary.md`, `runs.csv`, `summary.csv`, `comparison.csv`, `experiment.json`, `graphs/` |
| Application log (technical details, errors) | `logs/application.log` |
| Your settings | `config/user_settings.json` |

Earlier results are never overwritten: every experiment gets its own time-stamped folder.

## 7. Reading the results

* **Average waiting time (all vehicles)** is the main measure. Lower is better. It includes vehicles still stuck
  when the run ends, so leaving cars behind cannot make a controller look good.
* Numbers are written `mean ± half-width`, a 95 % confidence interval over the runs.
* **Improvement %** is positive when the agent is better than the baseline.
* **Verdict** says *better* or *worse* only when the seed-by-seed differences are clearly on one side; otherwise it says
  *no clear difference*. Trust the verdict over the percentage.
* Two baselines are shown. The **default** timer (30 s / 30 s) is weak for this traffic. The **tuned** timer uses green
  times found on separate seeds and is the honest one to compare against.
* *Total reward* uses the training formula, which penalises light switches; judge by waiting time and queue length.

## 8. Troubleshooting

| Problem | What to do |
|---|---|
| The window does not open and the program asks you to install pygame | `pip install -r requirements.txt`, then start again. |
| Graphs missing | `pip install matplotlib`. The numbers and CSV files are saved either way. |
| Agent buttons disabled | No model yet, or it is damaged: train one. The button's tooltip says which. |
| "A trained model already exists" | You are about to replace it. Choose *Continue the saved model* to keep what it learned. |
| Settings message listing problems | Fix the listed values; each says what is allowed. |
| Something unexpected | The app returns to the menu and logs details in `logs/application.log`. |
