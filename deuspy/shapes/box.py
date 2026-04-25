"""Box: an axis-aligned rectangular volume anchored at a corner."""

from __future__ import annotations

from dataclasses import dataclass, field

from deuspy.shapes.base import Shape
from deuspy.units import ORIGIN, Vec3


@dataclass
class Box(Shape):
    """A rectangular volume.

    length: extent in +X
    width:  extent in +Y
    height: extent into the stock — cut depth, taken as Z going from 0 down to -height.
    anchor: the (X, Y, Z=top) corner of the box. Defaults to the WCS origin (stock top).

    Conventions follow standard CNC: the WCS origin is at the top corner of the stock,
    +Z is up (away from the work), so cutting `height` units deep ends at Z = anchor.z - height.
    """

    length: float
    width: float
    height: float
    anchor: Vec3 = field(default=ORIGIN)

    def __post_init__(self) -> None:
        for name, value in [("length", self.length), ("width", self.width), ("height", self.height)]:
            if value <= 0:
                raise ValueError(f"Box.{name} must be > 0, got {value}")

    def bbox(self) -> tuple[Vec3, Vec3]:
        a = self.anchor
        lo = Vec3(a.x, a.y, a.z - self.height)
        hi = Vec3(a.x + self.length, a.y + self.width, a.z)
        return lo, hi
