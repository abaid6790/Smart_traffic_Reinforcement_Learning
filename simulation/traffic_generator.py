"""Creates new vehicles according to a traffic scenario.

Fair comparison between controllers depends on this class: the vehicles it
produces depend **only** on the seed, the scenario and the clock, never on what
the traffic light is doing.  Two simulations that use the same settings and seed
therefore receive exactly the same vehicles at exactly the same moments, whichever
controller is in charge.

Each road has its own random number stream, and every stream is advanced the
same way on every time step, so the roads do not influence each other.
"""

from __future__ import annotations

import math
import random

from config.settings import (
    ScenarioProfile,
    SimulationConfig,
    TrafficConfig,
    get_scenario,
)
from environment.enums import ALL_DIRECTIONS, Direction
from environment.vehicle import Vehicle


def resolve_rates(profile: ScenarioProfile, traffic: TrafficConfig) -> dict[Direction, float]:
    """Average arrivals per second on each road after applying the user's settings."""
    rates = {d: profile.rates[d.value] * traffic.rate_scale for d in ALL_DIRECTIONS}
    weights = traffic.direction_weights
    if weights is not None:
        total_rate = sum(rates.values())
        total_weight = sum(weights.get(d.value, 0.0) for d in ALL_DIRECTIONS)
        rates = {
            d: total_rate * weights.get(d.value, 0.0) / total_weight
            for d in ALL_DIRECTIONS
        }
    return rates


class TrafficGenerator:
    """Seeded source of vehicle arrivals for the four roads."""

    def __init__(
        self,
        traffic: TrafficConfig,
        simulation: SimulationConfig,
        seed: int | None = None,
    ) -> None:
        self.seed = traffic.seed if seed is None else seed
        self.profile = get_scenario(traffic.scenario)
        self._rates = resolve_rates(self.profile, traffic)
        self._max_vehicles = traffic.max_vehicles
        self._dt = simulation.dt
        self._base_speed = simulation.max_speed_ms
        self._speed_variation = simulation.speed_variation
        self._vehicle_length = simulation.vehicle_length

        self._arrival_rngs = {
            d: random.Random(f"arrivals:{self.seed}:{d.value}") for d in ALL_DIRECTIONS
        }
        phase_rng = random.Random(f"variation:{self.seed}")
        self._variation_phase = {
            d: phase_rng.uniform(0.0, 2.0 * math.pi) for d in ALL_DIRECTIONS
        }
        self._next_id = 1
        self.generated = 0

    def rate_at(self, direction: Direction, time: float) -> float:
        """Expected arrivals per second on ``direction`` at ``time``."""
        base = self._rates[direction]
        amplitude = self.profile.variation_amplitude
        if amplitude <= 0.0:
            return base
        angle = (
            2.0 * math.pi * time / self.profile.variation_period
            + self._variation_phase[direction]
        )
        return base * max(0.0, 1.0 + amplitude * math.sin(angle))

    def arrivals(self, now: float) -> list[Vehicle]:
        """Vehicles that arrive during the time step starting at ``now``."""
        new_vehicles: list[Vehicle] = []
        for direction in ALL_DIRECTIONS:
            rng = self._arrival_rngs[direction]
            draw = rng.random()  # always consumed, so streams stay aligned
            if self._max_vehicles is not None and self.generated >= self._max_vehicles:
                continue
            chance = 1.0 - math.exp(-self.rate_at(direction, now) * self._dt)
            if draw >= chance:
                continue
            factor = 1.0 + rng.uniform(-self._speed_variation, self._speed_variation)
            new_vehicles.append(
                Vehicle(
                    id=self._next_id,
                    direction=direction,
                    max_speed=self._base_speed * factor,
                    length=self._vehicle_length,
                    spawn_time=now,
                )
            )
            self._next_id += 1
            self.generated += 1
        return new_vehicles
