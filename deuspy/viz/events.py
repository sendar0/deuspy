"""Visualizer event dataclasses — the wire format between Machine and Viewer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from deuspy.units import Vec3

MoveKind = Literal["G0", "G1"]


@dataclass(frozen=True)
class ToolMoveEvent:
    target: Vec3
    kind: MoveKind


@dataclass(frozen=True)
class StockEvent:
    size: Vec3
    anchor: Vec3


@dataclass(frozen=True)
class ClearEvent:
    pass


@dataclass(frozen=True)
class AlarmEvent:
    message: str = ""


VizEvent = ToolMoveEvent | StockEvent | ClearEvent | AlarmEvent
