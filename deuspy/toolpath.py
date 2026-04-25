"""Toolpath: an ordered list of moves that can be emitted as G-code."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Literal

from deuspy import gcode
from deuspy.units import Vec3

MoveKind = Literal["G0", "G1"]


@dataclass(frozen=True)
class Move:
    kind: MoveKind
    target: Vec3
    feed: float | None = None  # only meaningful for G1; None means "use current modal F"

    def to_gcode(self) -> str:
        if self.kind == "G0":
            return gcode.rapid(x=self.target.x, y=self.target.y, z=self.target.z)
        return gcode.feed(x=self.target.x, y=self.target.y, z=self.target.z, f=self.feed)


@dataclass
class Toolpath:
    moves: list[Move] = field(default_factory=list)

    def add_rapid(self, target: Vec3) -> None:
        self.moves.append(Move("G0", target))

    def add_feed(self, target: Vec3, feed: float | None = None) -> None:
        self.moves.append(Move("G1", target, feed))

    def extend(self, other: Toolpath) -> None:
        self.moves.extend(other.moves)

    def iter_gcode(self) -> Iterator[str]:
        for m in self.moves:
            yield m.to_gcode()

    def __len__(self) -> int:
        return len(self.moves)

    def __iter__(self) -> Iterator[Move]:
        return iter(self.moves)
