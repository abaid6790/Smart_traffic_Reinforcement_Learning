"""Plays the RL environment with a *random* agent, to show that it works.

The random agent is not intelligent and is not a baseline for the comparison; it
only proves the environment can run full episodes safely.  Learning starts in Phase 6.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from config.settings import Settings
from environment.rl_env import ACTION_NAMES, NUM_STATES, TrafficEnv, describe_state, state_index


@dataclass
class EnvDemoResult:
    episodes: int
    returns: list[float]
    safety_violations: int
    decisions: int
    states_seen: int
    ignored_switches: int


def run_env_demo(settings: Settings, episodes: int = 3, agent_seed: int = 0,
                 print_fn=print, verbose_first: int = 6) -> EnvDemoResult:
    """Run ``episodes`` episodes with a random agent and print what happened."""
    if episodes < 1:
        raise ValueError("episodes must be at least 1")
    env = TrafficEnv(settings)
    rng = random.Random(agent_seed)
    rl = settings.rl
    print_fn("RL environment demo (random agent: it does NOT learn)")
    print_fn(f"Scenario {settings.traffic.scenario}, duration {settings.simulation.duration:g} s, "
             f"one decision every {rl.decision_interval:g} s")
    print_fn(f"{NUM_STATES} states = NS level x EW level x phase; "
             "actions: 0 KEEP, 1 SWITCH (only allowed after the minimum green)")
    print_fn(f"Levels: low < {rl.medium_traffic} <= medium < {rl.high_traffic} <= high "
             "(vehicles approaching a road pair)")
    print_fn("")

    returns: list[float] = []
    seen: set[int] = set()
    decisions = violations = ignored = 0
    base_seed = settings.traffic.seed
    for episode in range(episodes):
        state = env.reset(seed=base_seed + episode)
        total = 0.0
        shown = 0
        if episode == 0 and verbose_first:
            print_fn(f"First decisions of episode 1 (seed {env.seed}):")
        while True:
            action = rng.choice(env.valid_actions())
            before = state
            state, reward, done, info = env.step(action)
            total += reward
            decisions += 1
            ignored += info["switch_ignored"]
            seen.add(state_index(state))
            if episode == 0 and shown < verbose_first:
                shown += 1
                print_fn(f"  t={info['time']:6.1f}s  [{describe_state(before)}]  "
                         f"{ACTION_NAMES[action]:<6} -> reward {reward:+6.1f}  "
                         f"(waiting {info['waiting']})")
            if done:
                break
        metrics = env.episode_metrics()
        violations += metrics.safety_violations
        returns.append(total)
        waiting = "n/a" if metrics.average_waiting_time is None else f"{metrics.average_waiting_time:.1f} s"
        print_fn(f"Episode {episode + 1}: seed {env.seed}, return {total:+.1f}, "
                 f"served {metrics.vehicles_served}/{metrics.vehicles_arrived}, "
                 f"avg wait {waiting}, switches {metrics.light_switches}, "
                 f"safety conflicts {metrics.safety_violations}")
    print_fn("")
    print_fn(f"{decisions} decisions, {len(seen)} of {NUM_STATES} states visited, "
             f"{violations} safety conflicts "
             f"({'PASSED' if violations == 0 else 'FAILED'})")
    return EnvDemoResult(episodes, returns, violations, decisions, len(seen), ignored)
