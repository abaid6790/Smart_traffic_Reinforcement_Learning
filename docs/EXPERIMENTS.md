# Experiments (Phase 7)

`python main.py --experiment` compares controllers on identical traffic and writes the results to
`results/experiment_<time>_<scenarios>/`.

## The controllers

| Name | What it is |
|------|-----------|
| **Fixed-time (default)** | Plain timed signal, green times from your settings (`fixed.ns_green`/`ew_green`, default 30/30). |
| **Fixed-time (tuned)** | Same kind of controller, but its green times are found by a grid search per scenario on separate *tuning* seeds (candidates 10, 15, 20, 25, 30, 40, 50 s within the light's min/max green; the starting pair is always included). This is the honest baseline: the default 30/30 is weak for this traffic. |
| **Q-Learning** | The trained agent with exploration off (epsilon 0). Needs a model from `--train`; skip it with `--no-rl`. |

## Fairness

* Same scenario, duration and seed for every controller; traffic depends only on the seed, never on the light.
  After each scenario the program checks that every controller saw the same number of arriving vehicles
  ("traffic identical: yes" in the report).
* Three separate seed ranges: training `base+i`, evaluation `base+1,000,000+k`, tuning/validation
  `base+2,000,000+k`. The agent and the tuned baseline never see the evaluation traffic while being chosen.
* Safety conflicts are counted in every run; the command exits with an error if any occurs.

## Running

```powershell
python main.py --train --train-scenarios all --episodes 700
python main.py --experiment --experiment-scenarios all --runs 20
python main.py --experiment --runs 10 --experiment-scenarios low,high --no-tune --no-graphs
python main.py --experiment --no-rl          # fixed-time controllers only, no model needed
```

Options: `--runs N` (1-200), `--experiment-scenarios LIST|all`, `--no-tune`, `--no-rl`, `--no-graphs`,
`--results-dir DIR`, plus the usual `--seed`, `--duration`, `--model`.

## Output files

| File | Content |
|------|---------|
| `summary.md` | Readable report: tables of all metrics and every comparison with verdicts |
| `runs.csv` | One row per controller, scenario and run (seed, all metrics, total reward) |
| `summary.csv` | Mean, std and 95 % interval per scenario, controller and metric |
| `comparison.csv` | Improvement %, paired difference with interval, runs better/worse, verdict |
| `experiment.json` | Everything above plus settings, model information and tuning results |
| `graphs/` | Waiting time, queue and throughput bar charts; waiting time and vehicles over time per scenario |

Training also saves reward and queue graphs to `results/graphs/`. Graphs need `matplotlib`; without it
everything else still works.

## Statistics

Defined in `docs/METRICS.md`: mean ± 95 % Student-t interval, paired seed-by-seed comparison, improvement
formula on the means.

## Real results

20 runs per controller and scenario, 600 s each, base seed 42, one model trained for 700 episodes on all
scenarios. Average waiting time of all vehicles (lower is better):

| Scenario | Fixed (default) | Fixed (tuned) | Q-Learning | RL vs default | RL vs tuned |
|---|---:|---:|---:|---|---|
| low | 9.7 s | 6.3 s | 11.4 s | -17.1 % (worse) | -81.4 % (worse, 0/20 runs better) |
| medium | 10.5 s | 6.8 s | 7.3 s | +30.4 % (better) | -7.9 % (worse, 6/20 runs better) |
| high | 11.5 s | 7.8 s | 7.5 s | +34.7 % (better) | +3.4 % (no clear difference, 12/20) |
| rush_hour | 13.6 s | 12.1 s | 11.6 s | +14.6 % (better) | +3.8 % (better, 15/20) |
| balanced | 11.0 s | 7.0 s | 7.0 s | +36.6 % (better) | -0.5 % (no clear difference) |
| uneven | 12.1 s | 7.6 s | 7.6 s | +37.2 % (better) | -0.6 % (no clear difference) |
| random | 11.5 s | 7.7 s | 7.9 s | +31.6 % (better) | -1.6 % (no clear difference) |

![Average waiting time per scenario](images/experiment_waiting_time.png)

![Waiting time over a rush-hour run](images/experiment_rush_hour_over_time.png)

### What the results say

* The agent clearly beats the **default** 30/30 fixed-time controller in six of seven scenarios.
* That advantage is mostly a property of the weak baseline: a **tuned** fixed-time controller gets
  about the same result. Against it, Q-Learning is clearly better only in rush hour (+3.8 %), shows no clear
  difference in high, balanced, uneven and random traffic, and is **worse in low and medium traffic**.
* In low traffic the agent also has a much longer maximum waiting time (65.8 s vs 20.6 s tuned).
* Total reward ranks the controllers differently, because it penalises light switches; the tuned
  controller switches more often, so it scores worse on reward although vehicles wait less.

### Limits (be honest in the report)

* The tuned greens are mostly 10 s, the lowest candidate (the light's minimum green), so the tuning range
  itself limits how much better the baseline could be made.
* One model, one training run: another training seed could give somewhat different results.
* The state does not include how long the current green has lasted, and the reward (with its switch penalty)
  is not identical to the waiting-time metric. Both limit what the agent can learn; they are natural
  improvements for future work.
* Simplified simulation: one intersection, straight traffic only.
