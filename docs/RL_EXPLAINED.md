# Reinforcement learning explained (for this project)

A plain-language walk through the idea, with the project's real numbers. The exact definitions are in
[RL_ENVIRONMENT.md](RL_ENVIRONMENT.md) and [Q_LEARNING.md](Q_LEARNING.md).

## 1. The problem

A four-way intersection has one traffic light. A **fixed-time** light gives each direction a green of a set length
(30 s by default), whether or not any car is waiting. That wastes green time on empty roads. The question of the
project: *can a program learn, by trial and error, to give green to where the cars are, and does that really reduce
waiting?*

## 2. Reinforcement learning in one picture

```
        action (KEEP / SWITCH)
   ┌────────────────────────────┐
   │                            ▼
 Agent  ◄── state, reward ──  Environment (the simulated intersection)
```

Repeat many times: the agent looks at the **state**, chooses an **action**, the environment moves on, and the agent
receives a **reward** (a number: good or bad). Nobody tells the agent the right action. It only sees the rewards and
must work out which choices lead to more reward in the long run.

| RL word | In this project |
|---|---|
| Environment | The simulator wrapped as `TrafficEnv` (`environment/rl_env.py`) |
| State | 3 numbers: how busy North/South is (low/medium/high), how busy East/West is, and which pair has the green. 3 × 3 × 2 = **18 states** |
| Action | **KEEP** the current green or **SWITCH** to the other road pair |
| Step | One decision every 5 simulated seconds (plus the yellow and all-red time if a switch happens) |
| Reward | Fewer waiting cars is better; every light change and very long queues cost points |
| Episode | One full simulated run of 600 s |
| Policy | The rule "in this state, do this action" |

"Busy" counts the vehicles approaching a road pair that have not yet crossed the stop line: below 5 is *low*, 5 to 11 is
*medium*, 12 or more is *high* (the settings `rl.medium_traffic` and `rl.high_traffic`).

## 3. The reward

For each decision:

```
reward = (cars waiting before − cars waiting after)
         − 2.0 × (light changes during the decision)
         − 0.2 × max(0, cars waiting after − 30)
```

* The first part is positive when the queue shrinks and negative when it grows.
* The switch penalty discourages flickering: a change costs real time (yellow and all-red) during which nobody moves.
* The queue penalty pushes hard only when queues become very long.

The reward is a *guide* for learning, not the final score. The final score is measured separately in experiments
(average waiting time, queue length, ...), because the reward and the waiting time are not the same thing.

## 4. Q-Learning

The agent keeps a table, the **Q-table**: one row per state, one column per action, so 18 × 2 = 36 numbers.
`Q(state, action)` means *"how much total reward do I expect from here if I take this action and then play well?"*

Choosing an action uses the table; learning updates it after every decision:

```
Q(s, a) ← Q(s, a) + α × ( reward + γ × max Q(s′, a′) − Q(s, a) )
```

* α (`learning_rate`, 0.1): how far one experience moves the number.
* γ (`discount_factor`, 0.9): how much the future counts compared with the immediate reward.
* `max Q(s′, a′)`: the best value known in the state we ended up in.
* The part in brackets is the *surprise*: what happened (reward plus what we expect afterwards) minus what we expected.

**Worked example** (made-up numbers to show the arithmetic): suppose `Q = 0.0`, the reward was `−4.0` and the best
value in the next state is `1.5`. The target is `−4.0 + 0.9 × 1.5 = −2.65`; the surprise is `−2.65 − 0.0 = −2.65`; the new
value is `0.0 + 0.1 × (−2.65) = −0.265`. After many experiences the numbers settle down.

### Exploration versus exploitation

If the agent always took the best-known action it might never discover something better. So during training, with
probability **ε (epsilon)** it tries a random action; otherwise it takes the best one. Epsilon starts at 1.0
(everything random) and is multiplied by 0.995 after each episode down to a floor of 0.05. When the agent is *tested*,
epsilon is 0 and learning is off, so testing never changes the model.

### Why the best policy is kept, not the last

The greedy policy of a table that is still learning swings between good and poor, because the two actions' values are
close in busy states (measured in Phase 6, see Q_LEARNING.md). So every 20 episodes the current policy is tried on four
fixed validation runs, and the best one found is saved.

## 5. What the real model learned

The model used in the report (700 episodes on all seven scenarios) chose these actions (from `python main.py --model-info`):

| Traffic (NS, EW) | NS has green | EW has green |
|---|---|---|
| low, low | KEEP | KEEP |
| low, medium | SWITCH | KEEP |
| low, high | SWITCH | KEEP |
| medium, low | KEEP | SWITCH |
| medium, medium | KEEP | KEEP |
| medium, high | SWITCH | KEEP |
| high, low | KEEP | SWITCH |
| high, medium | KEEP | SWITCH |
| high, high | KEEP | KEEP |

Reading the table: it switches in exactly the six states where the road *without* the green is busier than the road
*with* it, and keeps the green otherwise. In other words the agent discovered, by itself, "give the green to the busier
road". That is sensible, and it is also a simple rule, which helps explain the results below.

## 6. What happened when it was compared

Real numbers, 20 runs per scenario on identical traffic (details and the statistics in [EXPERIMENTS.md](EXPERIMENTS.md)):

* Against the **default 30 s / 30 s timer** the agent lowered average waiting time clearly in six of seven scenarios
  (+15 % to +37 %), and was worse in low traffic (−17 %).
* Against a **tuned fixed-time timer** (best green lengths found on separate seeds) the agent was clearly better only in
  rush hour (+3.8 %), no different in four scenarios, and worse in low (−81 %) and medium (−8 %) traffic.

So most of the gain over the default timer came from the default timer being a poor setting for this traffic (shorter
greens already help a lot), not from the agent being clever. The honest conclusion is that this small agent is good, but
not better than a well-tuned timer in most cases.

## 7. Why it is not better, and what could be

* The state does not contain **how long the current green has lasted**, so the agent cannot learn "switch because we
  have already given this road enough time". Adding it (more states) is a natural next step.
* The reward and the waiting-time metric differ. The switch penalty may be too strong or too weak for some traffic.
* Only one training run, one model. Another training seed could give somewhat different results.
* A table cannot generalise: each of the 18 states is learned separately. Neural-network methods (DQN) could use finer
  information such as exact queue lengths per road, at the cost of much more complexity.
* Simplified world: one intersection, straight traffic only, no pedestrians.

## 8. Safety

The agent can only *request* a switch. The light refuses the request if the minimum green is not over, forces a switch
after the maximum green, and always runs yellow and all-red. Tests make an agent request a switch at every opportunity and
check that no safety rule is broken and no conflicting traffic ever enters the crossing.
