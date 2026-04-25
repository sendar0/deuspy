"""Engrave strategy: trace the outline at a single shallow depth."""

from __future__ import annotations

from dataclasses import dataclass

from deuspy.shapes.base import Shape
from deuspy.shapes.box import Box
from deuspy.strategies.base import MachineContext, Strategy
from deuspy.toolpath import Toolpath
from deuspy.units import Vec3


@dataclass
class Engrave(Strategy):
    """Trace the geometric outline at a single shallow depth.

    depth: positive number; the cutter goes to Z = anchor.z - depth.
    feed:  override the machine feed rate for this engraving (None → use machine feed).
    """

    depth: float = 0.1
    feed: float | None = None

    def plan(self, shape: Shape, ctx: MachineContext) -> Toolpath:
        if not isinstance(shape, Box):
            raise NotImplementedError(
                f"Engrave strategy v1 supports Box only, got {type(shape).__name__}"
            )
        if self.depth <= 0:
            raise ValueError(f"Engrave depth must be > 0, got {self.depth}")

        return _engrave_box(shape, ctx, self)


def _engrave_box(box: Box, ctx: MachineContext, strat: Engrave) -> Toolpath:
    tp = Toolpath()
    lo, hi = box.bbox()
    z = hi.z - strat.depth
    feed = strat.feed if strat.feed is not None else ctx.feed
    plunge = ctx.plunge_rate if ctx.plunge_rate is not None else feed

    tp.add_rapid(Vec3(lo.x, lo.y, ctx.safe_z))
    tp.add_feed(Vec3(lo.x, lo.y, z), plunge)
    for c in [
        Vec3(lo.x, hi.y, z),
        Vec3(hi.x, hi.y, z),
        Vec3(hi.x, lo.y, z),
        Vec3(lo.x, lo.y, z),
    ]:
        tp.add_feed(c, feed)
    tp.add_rapid(Vec3(lo.x, lo.y, ctx.safe_z))
    return tp
