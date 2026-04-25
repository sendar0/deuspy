"""Pocket strategy: clear the volume of a shape with a raster pattern."""

from __future__ import annotations

import math
from dataclasses import dataclass

from deuspy.shapes.base import Shape
from deuspy.shapes.box import Box
from deuspy.strategies.base import MachineContext, Strategy
from deuspy.toolpath import Toolpath
from deuspy.units import Vec3


@dataclass
class Pocket(Strategy):
    """Clear material from inside the shape's bounding box.

    stepdown: max depth removed per pass (current units). If None, takes the full
              height in one pass (only sensible for engraving-thin shapes).
    stepover: lateral step between raster lines, as a fraction of tool diameter
              (0 < stepover <= 1). Defaults to 0.4 (40%) — conservative.
    finish_pass: emit a perimeter cleanup pass at final depth.
    climb: climb mill (True) vs conventional (False). Affects raster direction.

    v1 implementation: simple zig-zag raster aligned to X. Only Box shapes are
    supported; other shapes raise NotImplementedError.
    """

    stepdown: float | None = None
    stepover: float = 0.4
    finish_pass: bool = True
    climb: bool = True

    def plan(self, shape: Shape, ctx: MachineContext) -> Toolpath:
        if not isinstance(shape, Box):
            raise NotImplementedError(
                f"Pocket strategy v1 supports Box only, got {type(shape).__name__}"
            )
        if not 0 < self.stepover <= 1:
            raise ValueError(f"stepover must be in (0, 1], got {self.stepover}")

        return _pocket_box(shape, ctx, self)


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
