# Development Plan

The project is built in small phases. Each phase is finished and tested before the
next one starts, and each ends with something you can run and check.

| # | Phase | Delivers | Done when |
|--:|-------|----------|-----------|
| 1 | Foundation | Folder structure, validated settings (JSON), logging, safe paths, `main.py` | `python main.py` runs; invalid settings give clear messages. **Done** |
| 2 | Headless simulation | Vehicle, Road, TrafficLight with safety rules, seeded traffic generator, Simulator, text demo | A full run is safe, repeatable and fast; tests prove no red-light running, overlap or conflicts. **Done** |
| 3 | Fixed controller + metrics | Fixed-time controller, metrics (waiting, queue, throughput, travel time, stops) | Same seed gives identical numbers; formulas documented and tested. **Done** |
| 4 | Visualisation | One Pygame window drawing the intersection, cars and lights from the existing simulator; speed control | You can watch the fixed controller and see cars queue without overlapping. **Done** |
| 5 | RL environment | `reset()`, `step()`, state discretisation, reward, safety enforcement | A random agent runs full episodes with no crashes or illegal phases. **Done** |
| 6 | Q-Learning + training | Q-table, epsilon-greedy, update rule, JSON save/load with validation, training loop with CSV log | Reward trends upward; saved model reloads correctly. **Done** |
| 7 | Evaluation | Test mode, experiment runner (same seeds for both controllers), improvement formulas, graphs, CSV/JSON export | Real fixed-vs-RL numbers across scenarios, also against a tuned fixed-time baseline. **Key milestone. Done** (see `docs/EXPERIMENTS.md`) |
| 8 | Menu and screens | Main menu, training, results, settings, about, side-by-side demo, one screen at a time | Every button works; none is a placeholder. **Done** (see `docs/USER_INTERFACE.md`) |
| 9 | Reliability pass | Input validation everywhere, corrupted/missing model handling, reset confirmations | Bad input never crashes the app |
| 10 | Tests and documentation | Remaining tests, project report, user/developer guides, RL explanation, viva questions | Docs match what the program really does |
| 11 | Final QA | Clean-environment install, full checklist, cleanup | Everything in the acceptance list passes |

## Decisions made so far (useful for the report and viva)

* **Simulation first, graphics later.** The simulator has no graphics, so it runs about
  10,000x faster than real time. That is what makes training thousands of episodes
  practical, and the window in Phase 4 only draws what the simulator already computed.
* **Safety lives in the light, not in the controller.** A controller can only request a
  switch; the light enforces minimum green, maximum green, yellow and all-red.
* **Fairness by construction.** Traffic depends only on seed, scenario and clock.
  Each road has its own random stream, so the controller cannot change which
  vehicles arrive.
* **No vehicle is ever lost.** Vehicles that cannot enter a full road wait in a backlog
  and keep accumulating waiting time.
* **Settings are validated, not trusted.** All values have documented ranges; errors are
  collected and shown together in plain English.
* **Time step:** 0.5 s per simulation step. The RL agent will decide every 5 s
  (`rl.decision_interval`), not every step, so learning is faster and the Q-table more
  stable.
* **One interface for all controllers.** A controller only looks at the simulator and may
  request a switch. The fixed-time and (later) Q-Learning controllers are run and
  measured by the same `run_episode` function, which keeps the comparison fair.
* **Honest metrics.** Two waiting-time averages are reported, so leaving vehicles stuck
  cannot flatter a controller, and an average that cannot be computed is `None`, never 0.
* **Experiments need many seeds.** Run-to-run variation of the baseline is about 7 %
  (rush hour, 20 seeds), so a single run proves nothing. The experiment phase will use
  10-20 runs per scenario.
* **The window only draws.** `ui.session` runs the same simulator as the headless runner
  and the picture interpolates between two steps, so watching cannot change results.
  Logic (geometry, snapshots, session) is plain Python and tested without pygame.
* **Never colour alone.** Signals carry text labels and vehicle colours have a legend.
* **Small state, honest reward.** 18 states (NS level x EW level x phase), 2 actions, reward =
  waiting reduction - switch penalty - excess-queue penalty. Details in `docs/RL_ENVIRONMENT.md`.
* **The agent only sees steady greens.** A step includes the yellow and all-red time after a
  switch, so the agent is never asked to decide during a transition, and a switch costs its real time.
* **Keep the best policy, not the last.** The greedy policy of a learning Q-table oscillates between good and
  poor; it is checked every 20 episodes on separate validation seeds and the best is kept (`docs/Q_LEARNING.md`).
* **Three seed ranges** (training, validation, evaluation) never overlap.
* **Compare against a tuned baseline too.** Fixed 12-20 s greens beat the default 30 s on this traffic, so an
  improvement over 30/30 alone would overstate the agent. Phase 7 adds a tuned fixed-time controller.
* **Experiments are paired and honest (Phase 7).** Every controller drives the same traffic per seed; results
  are means with 95 % confidence intervals plus a seed-by-seed comparison, and the verdict says "no clear
  difference" unless the interval of the paired difference excludes zero. Tuning uses its own seeds.
