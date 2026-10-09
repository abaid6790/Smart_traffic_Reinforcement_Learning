"""Names shared by the whole simulation.

A road is named after the side of the intersection vehicles come *from*:
vehicles on the NORTH road drive southwards towards the intersection.
"""

from __future__ import annotations

from enum import Enum


class Phase(Enum):
    """Which pair of roads may have a green light."""

    NS = "NS"  # north and south roads
    EW = "EW"  # east and west roads

    @property
    def other(self) -> Phase:
        return Phase.EW if self is Phase.NS else Phase.NS

    @classmethod
    def from_name(cls, name: str) -> Phase:
        return cls(name)


class Direction(Enum):
    """The four approach roads."""

    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"

    @property
    def phase(self) -> Phase:
        """The phase during which this road has the green light."""
        return Phase.NS if self in (Direction.NORTH, Direction.SOUTH) else Phase.EW

    @property
    def label(self) -> str:
        return self.value.capitalize()


ALL_DIRECTIONS: tuple[Direction, ...] = tuple(Direction)


class SignalColor(Enum):
    """What a driver sees."""

    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"


class LightStage(Enum):
    """Where the traffic light is in its cycle."""

    GREEN = "GREEN"  # current phase is green
    YELLOW = "YELLOW"  # current phase is clearing
    ALL_RED = "ALL_RED"  # every road is red, the crossing empties
