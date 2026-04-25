"""Hole: a small cylindrical bore intended for the PeckDrill strategy."""

from __future__ import annotations

from dataclasses import dataclass, field

from deuspy.shapes.base import Shape
from deuspy.units import ORIGIN, Vec3


@dataclass
class Hole(Shape):
    """A drilled hole.

    diameter: hole diameter (current units). The cutter must be smaller than this.
    depth:    how deep the hole goes (positive number; cut bottom = anchor.z - depth).
    anchor:   centre of the hole on the stock-top plane.
    """

    diameter: float
    depth: float
    anchor: Vec3 = field(default=ORIGIN)

    def __post_init__(self) -> None:
        if self.diameter <= 0:
            raise ValueError(f"Hole.diameter must be > 0, got {self.diameter}")
        if self.depth <= 0:
            raise ValueError(f"Hole.depth must be > 0, got {self.depth}")

    @property
    def radius(self) -> float:
        return self.diameter / 2.0

    def bbox(self) -> tuple[Vec3, Vec3]:
        a, r = self.anchor, self.radius
        lo = Vec3(a.x - r, a.y - r, a.z - self.depth)
        hi = Vec3(a.x + r, a.y + r, a.z)
        return lo, hi
