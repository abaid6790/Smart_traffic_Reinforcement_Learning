"""The headless simulator: roads + traffic light + traffic generator.

``Simulator`` knows nothing about windows or learning.  A controller (or a test)
drives it like this::

    sim = Simulator(settings)
    while not sim.finished:
        if some_condition:
            sim.light.request_switch()   # the light decides if it is allowed
        sim.step()

Because it has no graphics it runs much faster than real time, which is what
makes training practical.
"""

from __future__ import annotations

from config.settings import Settings
from environment.enums import ALL_DIRECTIONS, Direction, Phase
from environment.road import Road
from environment.traffic_light import TrafficLight
from environment.vehicle import Vehicle
from simulation.traffic_generator import TrafficGenerator

_EPS = 1e-9


class Simulator:
    """One four-way intersection with a traffic light and random traffic."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = (settings or Settings()).validate()
        self.reset()

    def reset(self, seed: int | None = None) -> None:
        """Start a fresh run.  ``seed`` overrides the seed in the settings."""
        cfg = self.settings
        self.time = 0.0
        self.step_count = 0
        self.roads: dict[Direction, Road] = {
            d: Road(d, cfg.simulation) for d in ALL_DIRECTIONS
        }
        self.light = TrafficLight(cfg.lights)
        self.generator = TrafficGenerator(cfg.traffic, cfg.simulation, seed=seed)
        self.completed: list[Vehicle] = []
        self.spawned = 0
        self.safety_violations = 0  # steps with crossing traffic in the box

    # ---- running ---------------------------------------------------------------

    @property
    def dt(self) -> float:
        return self.settings.simulation.dt

    @property
    def finished(self) -> bool:
        """True once the configured duration has been simulated."""
        return self.time >= self.settings.simulation.duration - _EPS

    def step(self) -> None:
        """Advance the whole simulation by one time step."""
        dt = self.dt
        for vehicle in self.generator.arrivals(self.time):
            self.roads[vehicle.direction].add_arrival(vehicle)
            self.spawned += 1

        for direction, road in self.roads.items():
            self.completed.extend(road.step(dt, self.light.color(direction)))
        self.light.update(dt)

        if self._crossing_conflict():
            self.safety_violations += 1
        self.time += dt
        self.step_count += 1

    def run(self, seconds: float | None = None) -> None:
        """Step until ``seconds`` more have passed (default: until finished)."""
        stop_at = (
            self.settings.simulation.duration if seconds is None else self.time + seconds
        )
        while self.time < stop_at - _EPS:
            self.step()

    # ---- questions controllers, metrics and the UI ask ---------------------------

    def queue_lengths(self) -> dict[Direction, int]:
        """Vehicles waiting at the stop line on each road."""
        return {d: road.queue_length() for d, road in self.roads.items()}

    def approach_counts(self) -> dict[Direction, int]:
        """Vehicles that have not yet crossed the stop line on each road."""
        return {d: road.approach_count() for d, road in self.roads.items()}

    def phase_queue(self, phase: Phase) -> int:
        """Total queue on the two roads served by ``phase``."""
        return sum(n for d, n in self.queue_lengths().items() if d.phase is phase)

    def vehicles_in_system(self) -> int:
        """Vehicles that have arrived but not yet left (including the backlog)."""
        return sum(len(r.vehicles) + len(r.backlog) for r in self.roads.values())

    def all_vehicles(self) -> list[Vehicle]:
        """Every vehicle that has arrived so far, in arrival order."""
        vehicles = list(self.completed)
        for road in self.roads.values():
            vehicles.extend(road.vehicles)
            vehicles.extend(road.backlog)
        return sorted(vehicles, key=lambda v: v.id)

    def summary(self) -> dict[str, object]:
        """A snapshot of the current state, handy for logging and display."""
        return {
            "time": self.time,
            "light": self.light.describe(),
            "queues": {d.value: n for d, n in self.queue_lengths().items()},
            "spawned": self.spawned,
            "completed": len(self.completed),
            "in_system": self.vehicles_in_system(),
            "switches": self.light.switch_count,
            "safety_violations": self.safety_violations,
        }

    # ---- safety ------------------------------------------------------------------------

    def _crossing_conflict(self) -> bool:
        """True if vehicles from both road pairs are in the crossing box at once."""
        in_box = {
            phase: any(
                self.roads[d].has_vehicle_in_box()
                for d in ALL_DIRECTIONS
                if d.phase is phase
            )
            for phase in Phase
        }
        return in_box[Phase.NS] and in_box[Phase.EW]
