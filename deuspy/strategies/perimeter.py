"""Perimeter strategy: cut the outline of a shape down to depth."""

from __future__ import annotations

import math
from dataclasses import dataclass

from deuspy.shapes.base import Shape
from deuspy.shapes.box import Box
from deuspy.shapes.cylinder import Cylinder
from deuspy.shapes.polyline import Polyline
from deuspy.strategies.base import MachineContext, Strategy
from deuspy.toolpath import Toolpath
from deuspy.units import Vec3


@dataclass
class Perimeter(Strategy):
    """Cut the outline of the shape, stepping deeper each pass.

    stepdown: max depth removed per pass.
    offset:   lateral cutter offset relative to the geometric outline.
              0 = on-line, +0.5 * tool_d = outside (cut shape free), -0.5 * tool_d = inside.
              Defaults to outside-of-line (cut the shape free) when None.
    climb: climb mill (CCW for outside) vs conventional.

    Supported shapes: Box, Cylinder, Polyline.
    """

    stepdown: float | None = None
    offset: float | None = None  # None → resolve to +tool_radius (outside cut)
    climb: bool = True

    def plan(self, shape: Shape, ctx: MachineContext) -> Toolpath:
        if isinstance(shape, Box):
            return _perimeter_box(shape, ctx, self)
        if isinstance(shape, Cylinder):
            return _perimeter_cylinder(shape, ctx, self)
        if isinstance(shape, Polyline):
            return _perimeter_polyline(shape, ctx, self)
        raise NotImplementedError(
            f"Perimeter supports Box, Cylinder, Polyline; got {type(shape).__name__}"
        )


def _perimeter_box(box: Box, ctx: MachineContext, strat: Perimeter) -> Toolpath:
    tp = Toolpath()
    lo, hi = box.bbox()
    r = ctx.tool_diameter / 2.0
    offset = strat.offset if strat.offset is not None else r

    x_lo, x_hi = lo.x - offset, hi.x + offset
    y_lo, y_hi = lo.y - offset, hi.y + offset

    total_depth = hi.z - lo.z
    stepdown = strat.stepdown if strat.stepdown is not None else total_depth
    n_steps = max(1, math.ceil(total_depth / stepdown))
    z_levels = [hi.z - min((i + 1) * stepdown, total_depth) for i in range(n_steps)]

    plunge_rate = ctx.plunge_rate if ctx.plunge_rate is not None else ctx.feed

    # Approach the start corner at safe Z.
    start = Vec3(x_lo, y_lo, ctx.safe_z)
    tp.add_rapid(start)

    for z in z_levels:
        tp.add_feed(Vec3(x_lo, y_lo, z), plunge_rate)
        if strat.climb:
            corners = [
                Vec3(x_lo, y_hi, z),
                Vec3(x_hi, y_hi, z),
                Vec3(x_hi, y_lo, z),
                Vec3(x_lo, y_lo, z),
            ]
        else:
            corners = [
                Vec3(x_hi, y_lo, z),
                Vec3(x_hi, y_hi, z),
                Vec3(x_lo, y_hi, z),
                Vec3(x_lo, y_lo, z),
            ]
        for c in corners:
            tp.add_feed(c, ctx.feed)

    tp.add_rapid(Vec3(x_lo, y_lo, ctx.safe_z))
    return tp


def _perimeter_cylinder(cyl: Cylinder, ctx: MachineContext, strat: Perimeter) -> Toolpath:
    tp = Toolpath()
    cx, cy, top_z = cyl.anchor.x, cyl.anchor.y, cyl.anchor.z
    tool_r = ctx.tool_diameter / 2.0
    offset = strat.offset if strat.offset is not None else tool_r
    cut_radius = cyl.radius + offset
    if cut_radius <= 0:
        raise ValueError(
            f"Resulting cut radius {cut_radius} <= 0; reduce |offset| or grow Cylinder."
        )

    total_depth = cyl.height
    stepdown = strat.stepdown if strat.stepdown is not None else total_depth
    n_steps = max(1, math.ceil(total_depth / stepdown))
    z_levels = [top_z - min((i + 1) * stepdown, total_depth) for i in range(n_steps)]

    plunge_rate = ctx.plunge_rate if ctx.plunge_rate is not None else ctx.feed
    start_xy = Vec3(cx + cut_radius, cy, ctx.safe_z)
    tp.add_rapid(start_xy)
    for z in z_levels:
        tp.add_feed(Vec3(cx + cut_radius, cy, z), plunge_rate)
        tp.add_arc(
            Vec3(cx + cut_radius, cy, z),
            center_offset=Vec3(-cut_radius, 0.0, 0.0),
            clockwise=strat.climb,
            feed=ctx.feed,
        )
    tp.add_rapid(Vec3(cx + cut_radius, cy, ctx.safe_z))
    return tp


def _perimeter_polyline(poly: Polyline, ctx: MachineContext, strat: Perimeter) -> Toolpath:
    """Trace the polyline at increasing depth.

    `offset` is ignored for polylines in v2 — proper outline-offset for arbitrary
    polygons requires Clipper-style polygon offsetting which we defer.
    """
    if strat.offset not in (None, 0.0):
        # Be loud rather than silently produce a wrong toolpath.
        raise NotImplementedError(
            "Perimeter offset for Polyline is not implemented in v2; pass offset=0 explicitly."
        )

    tp = Toolpath()
    if not poly.points:
        return tp
    pts = list(poly.points)
    if poly.closed and pts[0] != pts[-1]:
        pts.append(pts[0])

    top_z = pts[0].z
    total_depth = poly.depth
    stepdown = strat.stepdown if strat.stepdown is not None else total_depth
    n_steps = max(1, math.ceil(total_depth / stepdown))
    z_levels = [top_z - min((i + 1) * stepdown, total_depth) for i in range(n_steps)]

    plunge_rate = ctx.plunge_rate if ctx.plunge_rate is not None else ctx.feed
    first = pts[0]
    tp.add_rapid(Vec3(first.x, first.y, ctx.safe_z))

    for z in z_levels:
        tp.add_feed(Vec3(first.x, first.y, z), plunge_rate)
        for p in pts[1:]:
            tp.add_feed(Vec3(p.x, p.y, z), ctx.feed)

    tp.add_rapid(Vec3(first.x, first.y, ctx.safe_z))
    return tp
