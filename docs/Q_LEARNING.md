# Q-Learning agent and training (Phase 6)

## What the agent is

`agents/q_learning.py` is plain tabular Q-Learning. The Q-table has one row per state
(18, see [RL_ENVIRONMENT.md](RL_ENVIRONMENT.md)) and one column per action (KEEP, SWITCH):
36 numbers, each meaning "how much reward do I expect from here if I take this action".

| Function | What it does |
|---|---|
| `get_q_value(state, action)` | the stored number |
| `choose_action(state, valid_actions, explore)` | epsilon-greedy choice |
| `update(state, action, reward, next_state, ...)` | the learning rule below |
| `decay_epsilon()` | lowers epsilon after an episode |
| `reset()` | forgets everything |
| `save(path)` / `load(path)` | JSON model file, validated on load |

### The update rule

```
Q(s, a)  <-  Q(s, a) + learning_rate * ( reward + discount_factor * max Q(s', a')  -  Q(s, a) )
```

* The `max` is taken only over actions that can have an effect in the next state
  (a switch the light would refuse is not counted).
* Running out of simulated time is *not* treated as an ending, because the state does not
  contain the clock: the value of the next state is still used.
* One decision takes 5 s, or about 7 s when it includes a switch; the discount is applied
  per decision, not per second. This is a deliberate simplification.

### Exploration versus exploitation

* **Training:** with probability `epsilon` the agent tries a random valid action, otherwise
  the best one it knows (ties are broken randomly, so unknown states are explored fairly).
* `epsilon` starts at `rl.epsilon` (1.0) and is multiplied by `rl.epsilon_decay` (0.995) after
  every episode, never going below `rl.epsilon_min` (0.05).
* **Testing / running a trained agent:** epsilon is 0. The agent always uses what it learned
  (`explore=False`), and learning is switched off, so a test never changes the model.

## Training

```
python main.py --train --scenario rush_hour --episodes 500
python main.py --train --train-scenarios all --episodes 700        # mixed traffic
python main.py --train --continue-training --episodes 200           # keep training the saved model
python main.py --model-info                                         # what a model learned
python main.py --demo --controller rl --scenario rush_hour --seed 7
python main.py --window --controller rl                             # watch it in the window
```

All Q-Learning numbers can be changed in the `rl` settings or with `--learning-rate`,
`--discount`, `--epsilon`, `--epsilon-decay`, `--epsilon-min`, `--episodes`.
The model goes to `models/q_learning_model.json` (or `--model FILE`) and a per-episode CSV
log to `results/csv/training_<timestamp>.csv` (columns: episode, scenario, seed, epsilon,
total reward, decisions, waiting time, queue lengths, vehicles served, switches, safety
conflicts, q-table change, validation waiting time). An existing model is never
overwritten without `--force` or `--continue-training`. Ctrl+C stops safely and still saves.

`training/trainer.py` can also be paused, resumed and stopped from another thread
(`pause()`, `resume()`, `stop()`); a stop takes effect after the current episode. The training
screen of the application uses these.

### Seeds

Training episode *i* uses traffic seed `base_seed + i`. Tests and experiments use a separate
range starting 1,000,000 higher, and the checks made during training a third range starting
2,000,000 higher, so an agent is never judged on traffic it practised on.

### The model file

JSON with `format`, `version`, `saved_at`, the training information (episodes, scenarios,
base seed, final epsilon, best episode), the learning parameters, the reward parameters, the
state design (thresholds and decision interval) and the table. Loading checks everything: a
missing, damaged or foreign file gives a plain message instead of a crash, and a model
trained with different traffic thresholds or decision interval than the current settings is
refused, because its numbers would mean something else.

## Why the best policy is kept (an honest finding)

The first version simply used the final table. Testing it showed a problem: with several
training seeds and the same settings, only about one in four finished well; the others were
about 18 % *worse* than the fixed-time controller. Watching the policy during training explained
it. The greedy policy flips between a good one (average wait about 11.5 s in rush hour) and a
poor one (about 16 s) from one checkpoint to the next, in every run, e.g. for one seed:

```
episode: 20   40   60   80   100  120  140  160  180  200  220  240  260  280  300
wait s : 11.5 11.9 11.9 11.3 11.3 15.6 11.3 16.2 11.3 11.4 11.4 15.6 16.2 16.2 16.9
```

The Q-values of the two actions in the busiest states are nearly equal, so small updates flip
the choice. Higher discount factors, a lower learning rate and a different reward did not fix
it. So every `rl.validation_every` episodes (20) the current policy is tried, without
exploration, on `rl.validation_runs` (4) fixed validation runs, scored by the average waiting
time of all vehicles, and the best one found is kept and saved. After this, 8 of 8 training
seeds finished at +13 to +15 % in rush hour.

## Early results and their limits (not the final evaluation)

A first sanity check with 8 training seeds, evaluated on 10 separate traffic seeds against the
default fixed-time controller (30 s / 30 s), average waiting time of all vehicles:

| Scenario | fixed 30/30 | Q-Learning |
|---|---|---|
| rush hour (trained on rush hour, 300 episodes) | about 13.4 s | about 11.5 s (+13 to +15 %) |
| medium, high, balanced, uneven, random (one model trained on all scenarios, 400 episodes, 2 seeds) | 11-12 s | 7-8 s (about +31 to +39 %) |
| low (same models) | 10-11 s | 11 s (**3-10 % worse**) |

Important caveats (all handled in Phase 7):

1. **The default 30 s baseline is weak for this traffic.** Simply shortening the fixed greens helps
   a lot: in rush hour 15-20 s gives about 12.3 s, and in medium traffic 12 s gives 6.8 s (versus
   10.5 s at 30 s). Much of the agent's gain over 30/30 is therefore the *shorter cycle* it learned,
   not clever adaptation. Phase 7 therefore also compares against a **tuned** fixed-time
   controller (best green time found on separate seeds), and reports both.
2. These were 2-8 training seeds and 10 test seeds, a sanity check, not a result. Phase 7 uses
   20 runs per scenario with confidence intervals (see EXPERIMENTS.md).
3. In low traffic the agent is slightly worse than fixed-time; this is reported as it is in the final experiments.
4. The best policy was often found early (episode 20-120), which suggests the 18-state design
   limits what can be learned: it cannot see how long the green has lasted.
