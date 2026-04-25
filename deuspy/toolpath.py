"""Toolpath: an ordered list of moves that can be emitted as G-code."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Literal

from deuspy import gcode
from deuspy.units import Vec3

MoveKind = Literal["G0", "G1", "G2", "G3"]


@dataclass(frozen=True)
class Move:
    kind: MoveKind
    target: Vec3
    feed: float | None = None  # only meaningful for G1/G2/G3; None → use current modal F
    center_offset: Vec3 | None = None  # I,J,K relative offset from start; G2/G3 only

    def to_gcode(self) -> str:
        if self.kind == "G0":
            return gcode.rapid(x=self.target.x, y=self.target.y, z=self.target.z)
        if self.kind == "G1":
            return gcode.feed(x=self.target.x, y=self.target.y, z=self.target.z, f=self.feed)
        if self.center_offset is None:
            raise ValueError(f"{self.kind} arc requires center_offset (I/J/K)")
        clockwise = self.kind == "G2"
        return gcode.arc(
            x=self.target.x,
            y=self.target.y,
            z=self.target.z,
            i=self.center_offset.x,
            j=self.center_offset.y,
            k=self.center_offset.z,
            f=self.feed,
            clockwise=clockwise,
        )


@dataclass
class Toolpath:
    moves: list[Move] = field(default_factory=list)

    def add_rapid(self, target: Vec3) -> None:
        self.moves.append(Move("G0", target))

    def add_feed(self, target: Vec3, feed: float | None = None) -> None:
        self.moves.append(Move("G1", target, feed))

    def add_arc(
        self,
        target: Vec3,
        center_offset: Vec3,
        *,
        clockwise: bool = True,
        feed: float | None = None,
    ) -> None:
        kind: MoveKind = "G2" if clockwise else "G3"
        self.moves.append(Move(kind, target, feed, center_offset))

    def extend(self, other: Toolpath) -> None:
        self.moves.extend(other.moves)

    def iter_gcode(self) -> Iterator[str]:
        for m in self.moves:
            yield m.to_gcode()

    def __len__(self) -> int:
        return len(self.moves)

    def __iter__(self) -> Iterator[Move]:
        return iter(self.moves)
