# Roadmap

Ideas for after version 1.0.0, in the order of expected value. They are **ideas, not promises**, and none of them is built
yet. Each comes from a limitation found in the real results ([PROJECT_REPORT.md](PROJECT_REPORT.md)).

| # | Idea | Why | How to know it worked |
|---|---|---|---|
| 1 | Add the **elapsed green time** to the state (for example short, medium, long) | The agent cannot see how long a road has been waiting; in light traffic it left single vehicles waiting for up to 65.8 s | Lower maximum waiting time in low and uneven traffic without worse average waiting |
| 2 | **Tune the reward**, especially the switch penalty, and add a term for the longest wait | Reward and waiting time are different things; the switch penalty may make the agent reluctant to change for one vehicle | Re-run the 7-scenario experiment; compare against the tuned timer |
| 3 | **Train several models** (different seeds) and report the spread | The results come from one model | A confidence interval over models |
| 4 | **Widen the tuned baseline**: more candidate green times, more tuning seeds, separate NS and EW search | Most tuned greens sit at the lowest candidate, which equals the minimum green | A stronger baseline; the comparison stays honest |
| 5 | **Longer, more varied traffic**: saturated demand, uneven demand that changes over time | The scenarios are mostly not saturated, so throughput is equal for all controllers | Differences in throughput appear |
| 6 | **Function approximation (for example DQN)** with finer queue information | A table cannot generalise between states | Needs more training time and a fair comparison with the table |
| 7 | **Turns, pedestrians, several linked intersections** | A more realistic world | New scenarios and metrics |
| 8 | **Installable package** (`pip install`) and a command such as `traffic-rl` | Easier to share | Works from a clean machine |

## Rules for any item

* Changing the state or the reward invalidates the saved model and all results: retrain, re-run the experiments and replace
  every number in the documents ([CONTRIBUTING.md](../CONTRIBUTING.md)).
* Keep the three seed ranges separate and compare against the **tuned** baseline, not only the default timer.
* Report the result even if it is worse.
