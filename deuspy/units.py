"""Units, vectors, and unit-related constants."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum


class Unit(Enum):
    MM = "mm"
    INCH = "in"

    @property
    def gcode(self) -> str:
        return "G21" if self is Unit.MM else "G20"


MM = Unit.MM
INCH = Unit.INCH


class SpindleDirection(Enum):
    CW = "cw"
    CCW = "ccw"

    @property
    def gcode(self) -> str:
        return "M3" if self is SpindleDirection.CW else "M4"


CW = SpindleDirection.CW
CCW = SpindleDirection.CCW


@dataclass(frozen=True)
class Vec3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __add__(self, other: Vec3) -> Vec3:
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: Vec3) -> Vec3:
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> Vec3:
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)

    __rmul__ = __mul__

    def with_(self, *, x: float | None = None, y: float | None = None, z: float | None = None) -> Vec3:
        return Vec3(
            self.x if x is None else x,
            self.y if y is None else y,
            self.z if z is None else z,
        )

    @classmethod
    def from_iter(cls, it: Iterable[float]) -> Vec3:
        x, y, z = it
        return cls(x, y, z)


ORIGIN = Vec3(0.0, 0.0, 0.0)


_INCH_TO_MM = 25.4


def convert(value: float, src: Unit, dst: Unit) -> float:
    if src is dst:
        return value
    if src is Unit.INCH and dst is Unit.MM:
        return value * _INCH_TO_MM
    return value / _INCH_TO_MM


def convert_vec(v: Vec3, src: Unit, dst: Unit) -> Vec3:
    if src is dst:
        return v
    f = _INCH_TO_MM if (src is Unit.INCH and dst is Unit.MM) else 1.0 / _INCH_TO_MM
    return Vec3(v.x * f, v.y * f, v.z * f)
