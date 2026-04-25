"""Cylinder: a circular column anchored at the centre of its top face."""

from __future__ import annotations

from dataclasses import dataclass, field

from deuspy.shapes.base import Shape
from deuspy.units import ORIGIN, Vec3


@dataclass
class Cylinder(Shape):
    """An upright circular cylinder.

    radius: cylinder radius (current units).
    height: extent into the stock; the cylinder spans Z = anchor.z down to anchor.z - height.
    anchor: centre of the top face. Defaults to the WCS origin.
    """

    radius: float
    height: float
    anchor: Vec3 = field(default=ORIGIN)

    def __post_init__(self) -> None:
        if self.radius <= 0:
            raise ValueError(f"Cylinder.radius must be > 0, got {self.radius}")
        if self.height <= 0:
            raise ValueError(f"Cylinder.height must be > 0, got {self.height}")

    def bbox(self) -> tuple[Vec3, Vec3]:
        a, r = self.anchor, self.radius
        lo = Vec3(a.x - r, a.y - r, a.z - self.height)
        hi = Vec3(a.x + r, a.y + r, a.z)
        return lo, hi
