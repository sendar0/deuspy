"""Strategy ABC — turns a Shape + machine context into a Toolpath."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from deuspy.shapes.base import Shape
from deuspy.toolpath import Toolpath
from deuspy.units import Vec3


@dataclass(frozen=True)
class MachineContext:
    """Subset of Machine state that strategies need to plan a toolpath."""

    position: Vec3
    safe_z: float
    feed: float
    tool_diameter: float
    plunge_rate: float | None = None  # None → use feed


class Strategy(ABC):
    @abstractmethod
    def plan(self, shape: Shape, ctx: MachineContext) -> Toolpath:
        """Generate a Toolpath that realises `shape` according to this strategy."""
