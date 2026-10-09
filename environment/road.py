"""One approach road leading to the intersection.

Layout along the road (distances in metres from where vehicles enter):

    0 ........ stop line ==== crossing box ==== ........ end
              (road_length)   (intersection_length)  (exit_length)

Vehicles are kept in a list ordered from the front of the queue to the back, so
each vehicle only has to look at the one ahead of it.  Vehicles that arrive
while the road is full wait in a ``backlog`` outside the map instead of being
discarded; their waiting time still counts.  This keeps the comparison between
controllers fair, because no vehicle is ever lost.
"""

from __future__ import annotations

import math
from collections import deque

from config.settings import SimulationConfig
from environment.enums import Direction, SignalColor
from environment.vehicle import Vehicle

_EPS = 1e-9

# On yellow, a vehicle that could stop within this much extra distance must
# stop; only vehicles that truly cannot stop in time are allowed through.
_STOP_TOLERANCE = 0.5


class Road:
    """Vehicles approaching, crossing and leaving along one direction."""

    def __init__(self, direction: Direction, config: SimulationConfig) -> None:
        self.direction = direction
        self._config = config
        self.stop_line = config.road_length
        self.box_end = self.stop_line + config.intersection_length
        self.end = self.box_end + config.exit_length
        self.vehicles: list[Vehicle] = []  # front of the queue first
        self.backlog: deque[Vehicle] = deque()  # waiting for space to enter

    def reset(self) -> None:
        self.vehicles.clear()
        self.backlog.clear()

    # ---- running the road ---------------------------------------------------

    def add_arrival(self, vehicle: Vehicle) -> None:
        """A new vehicle has arrived; it enters as soon as there is room."""
        self.backlog.append(vehicle)

    def step(self, dt: float, signal: SignalColor) -> list[Vehicle]:
        """Move every vehicle for one time step; return those that left."""
        cfg = self._config
        self._admit_from_backlog(dt)

        finished: list[Vehicle] = []
        leader: Vehicle | None = None
        for vehicle in self.vehicles:  # from the front of the queue backwards
            limit = math.inf
            if leader is not None:
                limit = leader.rear - cfg.min_gap
            if vehicle.position <= self.stop_line + _EPS and not self._may_cross(
                vehicle, signal
            ):
                limit = min(limit, self.stop_line)
            vehicle.drive(
                dt,
                limit,
                cfg.acceleration,
                cfg.braking,
                cfg.halting_speed,
                self.stop_line,
                self.end,
            )
            if vehicle.completed:
                finished.append(vehicle)
            else:
                leader = vehicle
        if finished:
            self.vehicles = [v for v in self.vehicles if not v.completed]

        for vehicle in self.backlog:
            vehicle.wait_outside(dt, cfg.halting_speed)
        return finished

    def _may_cross(self, vehicle: Vehicle, signal: SignalColor) -> bool:
        """May this vehicle, still before the stop line, drive on across it?"""
        if signal is SignalColor.GREEN:
            return True
        if signal is SignalColor.RED:
            return False
        # Yellow: only go on if stopping comfortably is no longer possible.
        distance = self.stop_line - vehicle.position
        stopping = vehicle.stopping_distance(self._config.braking)
        return stopping > distance + _STOP_TOLERANCE

    def _admit_from_backlog(self, dt: float) -> None:
        """Let the next waiting vehicle onto the road if there is safe room."""
        if not self.backlog:
            return
        cfg = self._config
        vehicle = self.backlog[0]
        entry = vehicle.length  # whole vehicle starts inside the road
        if self.vehicles:
            last = self.vehicles[-1]
            entry_speed = min(vehicle.max_speed, last.speed)
            needed = (
                cfg.min_gap
                + entry_speed * entry_speed / (2.0 * cfg.braking)
                + entry_speed * dt
            )
            if last.rear - entry < needed:
                return
        else:
            entry_speed = vehicle.max_speed
        self.backlog.popleft()
        vehicle.position = entry
        vehicle.speed = entry_speed
        vehicle.entered = True
        self.vehicles.append(vehicle)

    # ---- questions other code asks ----------------------------------------------

    def queue_length(self) -> int:
        """Vehicles standing before the stop line, including those outside the map."""
        halting = self._config.halting_speed
        standing = sum(
            1
            for v in self.vehicles
            if v.position <= self.stop_line + _EPS and v.speed < halting
        )
        return standing + len(self.backlog)

    def approach_count(self) -> int:
        """All vehicles that have not yet crossed the stop line (moving or not)."""
        before = sum(1 for v in self.vehicles if v.position <= self.stop_line + _EPS)
        return before + len(self.backlog)

    def has_vehicle_in_box(self) -> bool:
        """True if any vehicle is (even partly) inside the crossing box."""
        for vehicle in self.vehicles:  # front first
            if vehicle.position <= self.stop_line:
                break  # everything further back has not reached the box
            if vehicle.rear < self.box_end:
                return True
        return False

    def vehicle_count(self) -> int:
        """Vehicles on the road, not counting the backlog."""
        return len(self.vehicles)
