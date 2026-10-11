# Glossary

| Term | Meaning in this project |
|---|---|
| **Action** | What the agent chooses every decision: KEEP the current green or SWITCH to the other road pair. |
| **Agent** | The Q-Learning program that chooses actions. |
| **All-red** | A short time (2 s by default) when every signal is red, so the crossing can clear between phases. |
| **Average waiting time (all vehicles)** | The main performance measure: mean waiting time of every vehicle that arrived, including those still waiting at the end. Lower is better. |
| **Baseline** | A controller to compare against. Here the default fixed timer and the tuned fixed timer. |
| **Best policy** | The policy with the lowest waiting time on validation traffic during training; this is what is saved. |
| **Confidence interval (95 %)** | A range around a mean that would contain the true mean in about 95 % of repeats of the experiment. Here Student's t over the runs. |
| **Decision interval** | Simulated time between two decisions of the agent (5 s). |
| **Discount factor (γ)** | How much future reward counts compared with immediate reward (0.9). |
| **Environment** | The simulated intersection seen through `reset()`, `step()` and a reward (`TrafficEnv`). |
| **Epsilon (ε)** | The probability that the agent explores with a random action while training. Starts at 1.0, decays by 0.995 per episode, minimum 0.05. |
| **Episode** | One full simulated run (600 s by default). |
| **Exploration / exploitation** | Trying something new versus using what is known to work. |
| **Fixed-time controller** | A timer that gives each direction a preset green regardless of traffic. |
| **Greedy policy** | Always choosing the action with the highest Q-value (epsilon 0). |
| **Learning rate (α)** | How far one experience moves a Q-value (0.1). |
| **Maximum green** | The light changes by itself after this time (60 s). |
| **Minimum green** | Switch requests are ignored until green has lasted this long (10 s). |
| **Paired comparison** | Comparing controllers run by run on the same seed, then looking at the differences. |
| **Phase (signal)** | Which road pair has the green: North/South or East/West. |
| **Policy** | The rule "in this state, take this action". |
| **Q-table** | The 18 × 2 table of expected rewards for each state and action. |
| **Q-value** | How much total reward the agent expects from a state if it takes an action and then plays well. |
| **Queue length** | Number of vehicles standing at a stop line. |
| **Reward** | The score after each decision: fall in waiting vehicles, minus 2.0 per switch, minus 0.2 per vehicle over a waiting limit of 30. |
| **Safety conflict** | Vehicles from crossing directions in the crossing at once. Always checked; always 0 in the reported runs. |
| **Scenario** | A traffic pattern: low, medium, high, rush hour, balanced, uneven, random. |
| **Seed** | A number that fixes the random traffic. The same seed gives the same cars. |
| **Seed ranges** | Training `base + i`, evaluation `base + 1,000,000 + k`, validation and tuning `base + 2,000,000 + k`. |
| **State** | What the agent sees: North/South traffic level, East/West traffic level (low, medium or high) and the current phase: 18 states. |
| **Throughput** | Vehicles that crossed per minute. |
| **Tuned fixed-time controller** | A fixed timer whose green times were chosen by grid search on separate seeds. |
| **Validation** | Trying the current policy on separate traffic during training to choose the best policy. |
| **Verdict** | "better", "worse" or "no clear difference", given by the paired comparison. |
| **Yellow** | The warning signal (5 s) before red. |
