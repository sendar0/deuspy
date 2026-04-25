"""Engrave strategy: trace the outline at a single shallow depth."""

from __future__ import annotations

from dataclasses import dataclass

from deuspy.shapes.base import Shape
from deuspy.shapes.box import Box
from deuspy.shapes.cylinder import Cylinder
from deuspy.shapes.polyline import Polyline
from deuspy.strategies.base import MachineContext, Strategy
from deuspy.toolpath import Toolpath
from deuspy.units import Vec3


@dataclass
class Engrave(Strategy):
    """Trace the geometric outline at a single shallow depth.

    depth: positive number; the cutter goes to Z = top.z - depth.
    feed:  override the machine feed rate for this engraving (None → use machine feed).

    Supported shapes: Box, Cylinder, Polyline.
    """

    depth: float = 0.1
    feed: float | None = None

    def plan(self, shape: Shape, ctx: MachineContext) -> Toolpath:
        if self.depth <= 0:
            raise ValueError(f"Engrave depth must be > 0, got {self.depth}")
        if isinstance(shape, Box):
            return _engrave_box(shape, ctx, self)
        if isinstance(shape, Cylinder):
            return _engrave_cylinder(shape, ctx, self)
        if isinstance(shape, Polyline):
            return _engrave_polyline(shape, ctx, self)
        raise NotImplementedError(
            f"Engrave supports Box, Cylinder, Polyline; got {type(shape).__name__}"
        )


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


def _engrave_cylinder(cyl: Cylinder, ctx: MachineContext, strat: Engrave) -> Toolpath:
    tp = Toolpath()
    cx, cy, top_z = cyl.anchor.x, cyl.anchor.y, cyl.anchor.z
    z = top_z - strat.depth
    feed = strat.feed if strat.feed is not None else ctx.feed
    plunge = ctx.plunge_rate if ctx.plunge_rate is not None else feed
    r = cyl.radius

    tp.add_rapid(Vec3(cx + r, cy, ctx.safe_z))
    tp.add_feed(Vec3(cx + r, cy, z), plunge)
    tp.add_arc(
        Vec3(cx + r, cy, z),
        center_offset=Vec3(-r, 0.0, 0.0),
        clockwise=True,
        feed=feed,
    )
    tp.add_rapid(Vec3(cx + r, cy, ctx.safe_z))
    return tp


def _engrave_polyline(poly: Polyline, ctx: MachineContext, strat: Engrave) -> Toolpath:
    tp = Toolpath()
    if not poly.points:
        return tp
    pts = list(poly.points)
    if poly.closed and pts[0] != pts[-1]:
        pts.append(pts[0])

    feed = strat.feed if strat.feed is not None else ctx.feed
    plunge = ctx.plunge_rate if ctx.plunge_rate is not None else feed
    top_z = pts[0].z
    z = top_z - strat.depth

    first = pts[0]
    tp.add_rapid(Vec3(first.x, first.y, ctx.safe_z))
    tp.add_feed(Vec3(first.x, first.y, z), plunge)
    for p in pts[1:]:
        tp.add_feed(Vec3(p.x, p.y, z), feed)
    tp.add_rapid(Vec3(first.x, first.y, ctx.safe_z))
    return tp
