"""Where things are on the screen.  Plain Python (no pygame needed).

The scene is seen from above with north at the top.  Everything is first worked out
in **metres relative to the centre of the intersection** (x to the right, y down)
and only then scaled to pixels, so the drawing code never repeats the road maths.

A vehicle's ``position`` in the simulator is the distance of its front bumper from
the start of its road.  Here it becomes ``d``, the distance along its direction of
travel measured from the centre of the crossing: ``d = position - (road_length +
intersection_length / 2)``.  So ``d = -box/2`` is the stop line and ``d = +box/2``
is where the vehicle leaves the crossing.
"""

from __future__ import annotations

from dataclasses import dataclass

from config.settings import Settings
from environment.enums import Direction

Point = tuple[float, float]

# Unit vector each vehicle travels along.  A vehicle on the NORTH road comes from
# the top of the screen and drives south (down), and so on.
_HEADINGS: dict[Direction, Point] = {
    Direction.NORTH: (0.0, 1.0),
    Direction.SOUTH: (0.0, -1.0),
    Direction.EAST: (-1.0, 0.0),
    Direction.WEST: (1.0, 0.0),
}

# A lane is this wide in the drawing.  Real lanes are about 3.5 m.
LANE_WIDTH = 3.5
# Vehicles are drawn a little wider than real ones so they stay visible.
VEHICLE_WIDTH = 2.2


def heading(direction: Direction) -> Point:
    """Unit vector (x, y) the vehicles on ``direction`` travel along."""
    return _HEADINGS[direction]


def lane_side(drive_on: str) -> float:
    """+1 when vehicles keep to the right of the road, -1 when they keep left."""
    return 1.0 if drive_on == "right" else -1.0


def right_of(vector: Point) -> Point:
    """The direction to the driver's right, for a driver heading along ``vector``.

    The screen's y axis points down, so this is a clockwise quarter turn.
    """
    return (-vector[1], vector[0])


@dataclass(frozen=True)
class RoadLayout:
    """The distances that describe the scene, in metres."""

    road_length: float
    intersection_length: float
    exit_length: float
    drive_on: str = "right"
    lane_width: float = LANE_WIDTH
    vehicle_width: float = VEHICLE_WIDTH

    @classmethod
    def from_settings(cls, settings: Settings) -> RoadLayout:
        sim = settings.simulation
        return cls(
            road_length=sim.road_length,
            intersection_length=sim.intersection_length,
            exit_length=sim.exit_length,
            drive_on=settings.display.drive_on,
        )

    @property
    def box_half(self) -> float:
        """Half the width of the crossing."""
        return self.intersection_length / 2.0

    @property
    def road_half_width(self) -> float:
        """Half the width of a road (it has one lane each way)."""
        return self.lane_width

    def d_of(self, position: float) -> float:
        """Distance from the centre of the crossing for a simulator ``position``."""
        return position - (self.road_length + self.box_half)

    def point(self, direction: Direction, d: float, lateral: float = 0.0) -> Point:
        """A point in metres: ``d`` along the direction of travel, ``lateral`` metres
        from the road's centre line towards the side this direction's vehicles use."""
        hx, hy = heading(direction)
        nx, ny = right_of((hx, hy))
        side = lane_side(self.drive_on) * lateral
        return (hx * d + nx * side, hy * d + ny * side)

    def lane_centre(self, direction: Direction, d: float) -> Point:
        """A point in the middle of the lane vehicles of ``direction`` drive in."""
        return self.point(direction, d, self.lane_width / 2.0)

    def vehicle_corners(
        self, direction: Direction, position: float, length: float
    ) -> list[Point]:
        """The four corners of a vehicle: front-left, front-right, rear-right, rear-left
        (as seen by the driver)."""
        front = self.d_of(position)
        rear = front - length
        half = self.vehicle_width / 2.0
        lane = self.lane_width / 2.0
        # lateral > 0 is towards the lane side, i.e. towards the driver's lane edge,
        # so the corner "left of the driver" has the smaller lateral value.
        return [
            self.point(direction, front, lane - half),
            self.point(direction, front, lane + half),
            self.point(direction, rear, lane + half),
            self.point(direction, rear, lane - half),
        ]

    def windshield_corners(
        self, direction: Direction, position: float, length: float
    ) -> list[Point]:
        """A small quadrilateral just behind the front bumper, so a vehicle visibly
        faces the way it is driving."""
        front = self.d_of(position)
        near = front - 0.25 * length
        far = front - 0.55 * length
        half = self.vehicle_width / 2.0 - 0.3
        lane = self.lane_width / 2.0
        return [
            self.point(direction, near, lane - half),
            self.point(direction, near, lane + half),
            self.point(direction, far, lane + half),
            self.point(direction, far, lane - half),
        ]

    def half_extent(self, view_range: float) -> float:
        """Metres from the centre to the edge of the picture along each road."""
        return self.box_half + view_range


@dataclass(frozen=True)
class ViewTransform:
    """Converts metres (relative to the centre) to pixels in a rectangle."""

    width: float
    height: float
    scale: float  # pixels per metre

    @property
    def centre(self) -> Point:
        return (self.width / 2.0, self.height / 2.0)

    def to_px(self, point: Point) -> tuple[float, float]:
        return (self.width / 2.0 + point[0] * self.scale,
                self.height / 2.0 + point[1] * self.scale)

    def length_px(self, metres: float) -> float:
        return metres * self.scale

    def visible_distance(self, direction: Direction) -> float:
        """How many metres of ``direction``'s road, measured from the centre, fit on
        screen."""
        hx, _ = heading(direction)
        along = self.width if hx else self.height
        return along / 2.0 / self.scale


def fit_view(width: float, height: float, half_extent: float) -> ViewTransform:
    """Scale so ``half_extent`` metres fit on each side of the centre in the
    shorter dimension of a ``width`` x ``height`` rectangle."""
    if width <= 0 or height <= 0 or half_extent <= 0:
        raise ValueError("width, height and half_extent must be positive.")
    return ViewTransform(width, height, min(width, height) / (2.0 * half_extent))
