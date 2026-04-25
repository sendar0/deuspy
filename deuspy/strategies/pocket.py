"""Pocket strategy: clear the volume of a shape."""

from __future__ import annotations

import math
from dataclasses import dataclass

from deuspy.shapes.base import Shape
from deuspy.shapes.box import Box
from deuspy.shapes.cylinder import Cylinder
from deuspy.strategies.base import MachineContext, Strategy
from deuspy.toolpath import Toolpath
from deuspy.units import Vec3


@dataclass
class Pocket(Strategy):
    """Clear material from inside the shape.

    stepdown: max depth removed per pass (current units). If None, takes the full
              height in one pass (only sensible for engraving-thin shapes).
    stepover: lateral step between raster lines or concentric circles, as a fraction
              of tool diameter (0 < stepover <= 1). Defaults to 0.4 (40%).
    finish_pass: emit a perimeter cleanup pass at final depth.
    climb: climb mill (True) vs conventional (False). Affects toolpath direction.

    Supported shapes: Box (zig-zag raster), Cylinder (concentric circles, inside-out).
    """

    stepdown: float | None = None
    stepover: float = 0.4
    finish_pass: bool = True
    climb: bool = True

    def plan(self, shape: Shape, ctx: MachineContext) -> Toolpath:
        if not 0 < self.stepover <= 1:
            raise ValueError(f"stepover must be in (0, 1], got {self.stepover}")
        if isinstance(shape, Box):
            return _pocket_box(shape, ctx, self)
        if isinstance(shape, Cylinder):
            return _pocket_cylinder(shape, ctx, self)
        raise NotImplementedError(
            f"Pocket strategy supports Box and Cylinder, got {type(shape).__name__}"
        )


def _pocket_box(box: Box, ctx: MachineContext, strat: Pocket) -> Toolpath:
    tp = Toolpath()
    lo, hi = box.bbox()
    r = ctx.tool_diameter / 2.0

    # Inset bounds by tool radius so the cutter doesn't overshoot the box.
    x_lo, x_hi = lo.x + r, hi.x - r
    y_lo, y_hi = lo.y + r, hi.y - r
    if x_hi <= x_lo or y_hi <= y_lo:
        raise ValueError(
            f"Tool diameter {ctx.tool_diameter} too large for box {box.length}x{box.width}"
        )

    # Z levels: top of box is hi.z, floor is lo.z. Step down in increments.
    total_depth = hi.z - lo.z
    stepdown = self_stepdown(strat, total_depth)
    n_steps = max(1, math.ceil(total_depth / stepdown))
    z_levels = [hi.z - min((i + 1) * stepdown, total_depth) for i in range(n_steps)]

    plunge_rate = ctx.plunge_rate if ctx.plunge_rate is not None else ctx.feed

    # Raster step in Y as fraction of tool diameter.
    step_y = strat.stepover * ctx.tool_diameter

    # Approach: rapid to (x_lo, y_lo, safe_z) above the start corner.
    tp.add_rapid(Vec3(x_lo, y_lo, ctx.safe_z))

    for z in z_levels:
        # Plunge to depth at the start corner.
        tp.add_feed(Vec3(x_lo, y_lo, z), plunge_rate)

        # Zig-zag raster: alternate direction each pass for efficiency.
        y = y_lo
        going_right = True
        while y <= y_hi + 1e-9:
            x_target = x_hi if going_right else x_lo
            tp.add_feed(Vec3(x_target, y, z), ctx.feed)

            # Step over in Y, unless we just finished the last pass.
            next_y = min(y + step_y, y_hi)
            if next_y <= y + 1e-9:
                break
            tp.add_feed(Vec3(x_target, next_y, z), ctx.feed)
            y = next_y
            going_right = not going_right

        if strat.finish_pass:
            # Climb-mill perimeter cleanup at this depth.
            _emit_perimeter(tp, x_lo, y_lo, x_hi, y_hi, z, ctx.feed, climb=strat.climb)

        # Retract to safe Z before the next level (or completion).
        tp.add_rapid(Vec3(x_lo, y_lo, ctx.safe_z))

    return tp


def self_stepdown(strat: Pocket, total_depth: float) -> float:
    return strat.stepdown if strat.stepdown is not None else total_depth


def _emit_perimeter(
    tp: Toolpath,
    x_lo: float,
    y_lo: float,
    x_hi: float,
    y_hi: float,
    z: float,
    feed: float,
    *,
    climb: bool,
) -> None:
    """Emit a closed rectangular perimeter at depth z, returning to start."""
    if climb:
        corners = [
            Vec3(x_lo, y_lo, z),
            Vec3(x_lo, y_hi, z),
            Vec3(x_hi, y_hi, z),
            Vec3(x_hi, y_lo, z),
            Vec3(x_lo, y_lo, z),
        ]
    else:
        corners = [
            Vec3(x_lo, y_lo, z),
            Vec3(x_hi, y_lo, z),
            Vec3(x_hi, y_hi, z),
            Vec3(x_lo, y_hi, z),
            Vec3(x_lo, y_lo, z),
        ]
    for c in corners:
        tp.add_feed(c, feed)


def _pocket_cylinder(cyl: Cylinder, ctx: MachineContext, strat: Pocket) -> Toolpath:
    """Clear a cylindrical volume with concentric circles, working outward.

    For each Z level: plunge at centre, then expand outward in stepover increments,
    closing each ring with a single G2 arc back to its start.
    """
    tp = Toolpath()
    cx, cy, top_z = cyl.anchor.x, cyl.anchor.y, cyl.anchor.z
    tool_r = ctx.tool_diameter / 2.0
    r_max = cyl.radius - tool_r
    if r_max <= 0:
        raise ValueError(
            f"Tool diameter {ctx.tool_diameter} too large for Cylinder radius {cyl.radius}"
        )

    total_depth = cyl.height
    stepdown = strat.stepdown if strat.stepdown is not None else total_depth
    n_steps = max(1, math.ceil(total_depth / stepdown))
    z_levels = [top_z - min((i + 1) * stepdown, total_depth) for i in range(n_steps)]

    plunge_rate = ctx.plunge_rate if ctx.plunge_rate is not None else ctx.feed
    step = strat.stepover * ctx.tool_diameter

    tp.add_rapid(Vec3(cx, cy, ctx.safe_z))

    for z in z_levels:
        # Plunge at centre.
        tp.add_feed(Vec3(cx, cy, z), plunge_rate)
        # Expand outward in concentric rings.
        r = step
        while r < r_max:
            tp.add_feed(Vec3(cx + r, cy, z), ctx.feed)
            tp.add_arc(
                Vec3(cx + r, cy, z),
                center_offset=Vec3(-r, 0.0, 0.0),
                clockwise=strat.climb,
                feed=ctx.feed,
            )
            r += step
        # Final outermost ring at r_max (the cleanup / finish pass).
        if strat.finish_pass or r >= r_max:
            tp.add_feed(Vec3(cx + r_max, cy, z), ctx.feed)
            tp.add_arc(
                Vec3(cx + r_max, cy, z),
                center_offset=Vec3(-r_max, 0.0, 0.0),
                clockwise=strat.climb,
                feed=ctx.feed,
            )
        tp.add_rapid(Vec3(cx, cy, ctx.safe_z))

    return tp
