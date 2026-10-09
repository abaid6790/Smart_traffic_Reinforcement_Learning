"""A single simulated vehicle.

Vehicles live on a one-dimensional path.  ``position`` is the distance of the
vehicle's *front bumper* from the start of its road, in metres.  The stop line
sits at ``road_length``; the crossing box follows it; the vehicle disappears
once its front bumper passes the end of the exit road.

For simplicity every vehicle drives straight through the intersection.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from environment.enums import Direction

_EPS = 1e-9

# A vehicle only counts a *new* stop after it has first got back up to this
# multiple of the halting speed.  Without it, a queue creeping forward would be
# counted as many separate stops.
_RESUME_FACTOR = 2.0


@dataclass
class Vehicle:
    """State and motion of one vehicle."""

    id: int
    direction: Direction
    max_speed: float  # this driver's preferred speed (m/s)
    length: float  # (m)
    spawn_time: float = 0.0  # when the vehicle arrived (s)
    position: float = 0.0  # front bumper, metres from the start of the road
    speed: float = 0.0  # (m/s)
    waiting_time: float = 0.0  # seconds spent standing before the stop line
    travel_time: float = 0.0  # seconds since arrival (until it leaves)
    stops: int = 0  # number of separate times the vehicle came to a halt
    stopped: bool = False  # currently below the halting speed
    completed: bool = False  # has left the simulation
    entered: bool = False  # is on the road (False while waiting to enter)
    _armed: bool = field(default=True, init=False, repr=False)

    @property
    def rear(self) -> float:
        """Position of the rear bumper."""
        return self.position - self.length

    def stopping_distance(self, braking: float) -> float:
        """Distance needed to stop from the current speed at ``braking`` m/s^2."""
        return self.speed * self.speed / (2.0 * braking)

    def drive(
        self,
        dt: float,
        limit: float,
        acceleration: float,
        braking: float,
        halting_speed: float,
        stop_line: float,
        end_position: float,
    ) -> None:
        """Advance one time step.

        ``limit`` is the furthest position the front bumper may reach: the stop
        line when the signal says stop, the rear of the vehicle ahead (minus the
        minimum gap), or ``math.inf`` when nothing is in the way.  The vehicle
        slows down early enough to stop in time, and is never allowed to move
        past ``limit``.
        """
        if self.completed:
            return
        target = min(self.max_speed, self.speed + acceleration * dt)
        if math.isfinite(limit):
            gap = max(0.0, limit - self.position)
            # Fastest speed from which the vehicle can still stop within the gap
            # after travelling for one more time step.
            safe = braking * (math.sqrt(dt * dt + 2.0 * gap / braking) - dt)
            target = min(target, safe)
        new_position = min(self.position + target * dt, max(limit, self.position))
        self.speed = (new_position - self.position) / dt
        self.position = new_position
        self.travel_time += dt
        self._record_motion(dt, halting_speed, self.position <= stop_line + _EPS)
        if self.position >= end_position:
            self.completed = True

    def wait_outside(self, dt: float, halting_speed: float) -> None:
        """Account for a time step spent waiting to enter a full road."""
        self.speed = 0.0
        self.travel_time += dt
        self._record_motion(dt, halting_speed, before_stop_line=True)

    def _record_motion(self, dt: float, halting_speed: float, before_stop_line: bool) -> None:
        halted = self.speed < halting_speed
        if self.speed >= halting_speed * _RESUME_FACTOR:
            self._armed = True
        if halted:
            if self._armed:
                self.stops += 1
                self._armed = False
            if before_stop_line:
                self.waiting_time += dt
        self.stopped = halted
