"""Frozen copies of the simulator's state, for smooth drawing.  Plain Python.

The simulator moves in steps (0.5 s by default), which would look jerky at 60 frames
per second.  Instead the window keeps the state *before* the latest step and the
state *after* it, and draws vehicles somewhere between the two.  ``alpha`` says how
far through the step the picture is: 0 is the earlier state, 1 is the later one.

The signal colours drawn are those of the earlier state, because those are the
colours the vehicles actually obeyed during the step.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from environment.enums import ALL_DIRECTIONS, Direction, LightStage, Phase, SignalColor

if TYPE_CHECKING:
    from simulation.simulator import Simulator


@dataclass(frozen=True)
class VehicleView:
    """What the drawing code needs to know about one vehicle."""

    id: int
    direction: Direction
    position: float  # front bumper, metres from the start of its road
    length: float
    waiting: bool  # standing still before the stop line


@dataclass(frozen=True)
class Snapshot:
    """The state of the simulation at one moment."""

    time: float
    vehicles: dict[int, VehicleView]
    signals: dict[Direction, SignalColor]
    phase: Phase
    stage: LightStage
    stage_time: float  # seconds the light has been in this stage
    queues: dict[Direction, int]
    outside: dict[Direction, int]  # vehicles waiting beyond the start of the road


def capture(sim: Simulator) -> Snapshot:
    """Take a snapshot of ``sim``."""
    stop_line = sim.settings.simulation.road_length
    vehicles: dict[int, VehicleView] = {}
    for direction, road in sim.roads.items():
        for v in road.vehicles:
            vehicles[v.id] = VehicleView(
                id=v.id,
                direction=direction,
                position=v.position,
                length=v.length,
                waiting=v.stopped and v.position <= stop_line,
            )
    light = sim.light
    return Snapshot(
        time=sim.time,
        vehicles=vehicles,
        signals=light.colors(),
        phase=light.phase,
        stage=light.stage,
        stage_time=light.stage_time,
        queues=sim.queue_lengths(),
        outside={d: len(sim.roads[d].backlog) for d in ALL_DIRECTIONS},
    )


def interpolate(previous: Snapshot, current: Snapshot, alpha: float) -> list[VehicleView]:
    """Vehicles as they should be drawn, ``alpha`` of the way from ``previous`` to
    ``current`` (0 <= alpha <= 1).

    * a vehicle in both snapshots is placed between its two positions;
    * a vehicle that only exists in ``current`` (it just entered) is drawn where it is;
    * a vehicle that only existed in ``previous`` has just left and is not drawn.
    """
    alpha = max(0.0, min(1.0, alpha))
    drawn: list[VehicleView] = []
    for vehicle_id, now in current.vehicles.items():
        before = previous.vehicles.get(vehicle_id)
        if before is None:
            drawn.append(now)
            continue
        position = before.position + (now.position - before.position) * alpha
        waiting = before.waiting if alpha < 0.5 else now.waiting
        drawn.append(VehicleView(vehicle_id, now.direction, position, now.length, waiting))
    return drawn
