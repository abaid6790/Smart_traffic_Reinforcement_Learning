# RL environment (Phase 5)

`environment/rl_env.py` turns the simulator into the usual reinforcement-learning loop.

```python
env = TrafficEnv(settings)
state = env.reset(seed=7)
while True:
    state, reward, done, info = env.step(action)   # action: KEEP (0) or SWITCH (1)
    if done:
        break
```

Also available: `get_state()`, `calculate_reward()`, `valid_actions()`, `snapshot()`
(current traffic, phase, waiting vehicles, queues, vehicles served, time) and
`episode_metrics()` (the same measurements the fixed-time controller gets).

## State: 18 values

`(NS level, EW level, phase)`

* **Level** of a road pair = vehicles approaching it that have not yet crossed the stop
  line (moving or waiting, plus any waiting outside a full road), added over its two roads.
  `0 = low` below `rl.medium_traffic` (default 5), `1 = medium` from there to below
  `rl.high_traffic` (default 12), `2 = high` from 12 up.
  The defaults were chosen from measured data: across the seven scenarios the typical
  count runs from about 1-3 (low traffic) to about 15-25 (rush hour).
* **Phase**: 0 = North/South has the green, 1 = East/West has it.
* 3 x 3 x 2 = 18 states, so a Q-table has 18 x 2 = 36 numbers.
  `state_index()` gives each state its row number 0-17.

Example: `(2, 0, 0)` = "NS traffic high, EW traffic low, NS has green".

## Actions

`0 = KEEP` the current phase, `1 = SWITCH` to the other one. The agent never sets
timers. A switch is only a *request*; the traffic light accepts it only when the light is
green and the minimum green time has passed, and then runs yellow and all-red by itself.
`valid_actions()` lists `[KEEP]` while a switch would be refused. If an agent asks anyway,
the request is ignored (it behaves exactly like KEEP, without penalty) and
`info["switch_ignored"]` is `True`; nothing crashes and no rule is bent.

## What one step is

1. Apply the action.
2. Simulate `rl.decision_interval` seconds (default 5).
3. If a switch is under way (yellow + all-red = 7 s by default), keep going until the new
   green begins. So **the agent only ever sees states with a steady green light**, and a
   switch costs the real transition time, during which the other road is still waiting.
4. The episode ends exactly at `simulation.duration`.

The maximum green (60 s) still applies: if the agent keeps choosing KEEP the light
changes by itself, and that change counts as a switch in the reward.

## Reward

For each decision:

```
reward = (waiting before - waiting after)
         - switch_penalty x (light switches during the decision)
         - queue_penalty  x max(0, waiting after - queue_limit)
```

* *waiting* = vehicles standing at a stop line + vehicles waiting outside a full road
  (so overflow cannot be hidden).
* Defaults: `switch_penalty = 2.0`, `queue_limit = 30`, `queue_penalty = 0.2`.
* `env.reward_breakdown()` and `info["reward_parts"]` give the three parts separately.

Why this shape: the first term rewards fewer waiting vehicles (lower waiting time, shorter
queues, more vehicles served); the second discourages flickering; the third pushes hard
when queues are really long. All numbers are in the `rl` section of the settings.

Known limit: new arrivals raise *waiting* regardless of what the agent does, so rewards
are noisy; learning has to average this out over many episodes.

## Fairness and safety

* Traffic depends only on seed and scenario, never on the agent
  (a test plays "always KEEP" and "always SWITCH" and checks identical arrivals).
* Safety is enforced by the traffic light, not by the agent. Tests make an agent request a
  switch at every chance and check the minimum green is respected and the simulator's
  crossing-conflict check never fires.

## Try it

```
python main.py --env-demo --scenario rush_hour --duration 300 --env-episodes 3
```

This plays a **random** agent. It does not learn and is not the comparison baseline; it
only shows that full episodes run safely. The learning agent is in `agents/q_learning.py`
(see Q_LEARNING.md).
