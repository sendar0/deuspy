"""Polyline: an ordered list of 2D points extruded to a depth."""

from __future__ import annotations

from dataclasses import dataclass, field

from deuspy.shapes.base import Shape
from deuspy.units import ORIGIN, Vec3


@dataclass
class Polyline(Shape):
    """An ordered sequence of 2D points (sharing one Z) treated as a 2.5D feature.

    points:  ordered Vec3s. All points should share the same Z (the top face).
             If they don't, the first point's Z is used as the top.
    depth:   how deep below the top to cut (positive number).
    closed:  if True, treat the polyline as a closed polygon (first==last on emit).

    `Polyline` is the v2 catch-all for arbitrary 2D outlines. Pocket-clearing arbitrary
    polygons needs proper polygon-offset machinery and is deferred. Perimeter and
    Engrave both work today.
    """

    points: list[Vec3] = field(default_factory=list)
    depth: float = 1.0
    closed: bool = True

    def __post_init__(self) -> None:
        if self.depth <= 0:
            raise ValueError(f"Polyline.depth must be > 0, got {self.depth}")
        if len(self.points) < 2:
            raise ValueError("Polyline needs at least 2 points")

    def bbox(self) -> tuple[Vec3, Vec3]:
        xs = [p.x for p in self.points]
        ys = [p.y for p in self.points]
        top_z = self.points[0].z
        return (
            Vec3(min(xs), min(ys), top_z - self.depth),
            Vec3(max(xs), max(ys), top_z),
        )

    @classmethod
    def rectangle(cls, length: float, width: float, *, depth: float, anchor: Vec3 = ORIGIN) -> Polyline:
        """Convenience factory: a closed 4-point rectangle anchored at one corner."""
        a = anchor
        pts = [
            Vec3(a.x, a.y, a.z),
            Vec3(a.x + length, a.y, a.z),
            Vec3(a.x + length, a.y + width, a.z),
            Vec3(a.x, a.y + width, a.z),
        ]
        return cls(points=pts, depth=depth, closed=True)

    @classmethod
    def star(
        cls,
        *,
        points: int = 5,
        outer_radius: float,
        inner_radius: float,
        depth: float,
        anchor: Vec3 = ORIGIN,
        rotation: float = 0.0,
    ) -> Polyline:
        """Regular n-pointed star centred on `anchor`.

        points:        number of star tips (≥3).
        outer_radius:  distance from centre to a tip.
        inner_radius:  distance from centre to a valley between tips.
        rotation:      rotation in radians; 0 puts the first tip on +Y.
        """
        import math

        if points < 3:
            raise ValueError(f"Star needs ≥3 points, got {points}")
        if outer_radius <= 0 or inner_radius <= 0:
            raise ValueError("Star radii must be > 0")
        if inner_radius >= outer_radius:
            raise ValueError("inner_radius must be < outer_radius")

        verts: list[Vec3] = []
        # 2*points vertices alternating outer / inner.
        for i in range(2 * points):
            r = outer_radius if i % 2 == 0 else inner_radius
            angle = rotation + math.pi / 2 + i * math.pi / points
            verts.append(
                Vec3(
                    anchor.x + r * math.cos(angle),
                    anchor.y + r * math.sin(angle),
                    anchor.z,
                )
            )
        return cls(points=verts, depth=depth, closed=True)
