"""Perimeter strategy: cut the outline of a shape down to depth."""

from __future__ import annotations

import math
from dataclasses import dataclass

from deuspy.shapes.base import Shape
from deuspy.shapes.box import Box
from deuspy.strategies.base import MachineContext, Strategy
from deuspy.toolpath import Toolpath
from deuspy.units import Vec3


@dataclass
class Perimeter(Strategy):
    """Cut the outline of the shape, stepping deeper each pass.

    stepdown: max depth removed per pass.
    offset:   lateral cutter offset relative to the geometric outline.
              0 = on-line, +0.5 * tool_d = outside (cut shape free), -0.5 * tool_d = inside.
              Defaults to outside-of-line (cut the box free) once a tool diameter is known.
    climb: climb mill (CCW for outside) vs conventional.
    """

    stepdown: float | None = None
    offset: float | None = None  # None → resolve to +tool_radius (outside cut)
    climb: bool = True

    def plan(self, shape: Shape, ctx: MachineContext) -> Toolpath:
        if not isinstance(shape, Box):
            raise NotImplementedError(
                f"Perimeter strategy v1 supports Box only, got {type(shape).__name__}"
            )
        return _perimeter_box(shape, ctx, self)


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
