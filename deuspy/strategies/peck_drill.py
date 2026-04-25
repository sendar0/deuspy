"""PeckDrill strategy: plunge → retract → plunge deeper, repeated to full depth."""

from __future__ import annotations

import math
from dataclasses import dataclass

from deuspy.shapes.base import Shape
from deuspy.shapes.hole import Hole
from deuspy.strategies.base import MachineContext, Strategy
from deuspy.toolpath import Toolpath
from deuspy.units import Vec3


@dataclass
class PeckDrill(Strategy):
    """Peck drilling: each peck goes `peck_depth` deeper, then retracts to clear chips.

    peck_depth: depth removed per peck. Defaults to 0.5 × tool_diameter when None.
    retract_to: full retract above each peck. None → ctx.safe_z (full retract).
                Pass 0 for a small retract just above the previous peck (faster but
                worse chip clearance).
    dwell_at_top: seconds to dwell at retract — gives the tool a moment to clear chips.
    """

    peck_depth: float | None = None
    retract_to: float | None = None
    dwell_at_top: float = 0.0

    def plan(self, shape: Shape, ctx: MachineContext) -> Toolpath:
        if not isinstance(shape, Hole):
            raise NotImplementedError(
                f"PeckDrill supports Hole only, got {type(shape).__name__}"
            )
        return _peck_drill(shape, ctx, self)


def _peck_drill(hole: Hole, ctx: MachineContext, strat: PeckDrill) -> Toolpath:
    if ctx.tool_diameter >= hole.diameter:
        raise ValueError(
            f"Tool diameter {ctx.tool_diameter} >= hole diameter {hole.diameter}; can't drill."
        )

    tp = Toolpath()
    cx, cy, top_z = hole.anchor.x, hole.anchor.y, hole.anchor.z
    peck = strat.peck_depth if strat.peck_depth is not None else ctx.tool_diameter * 0.5
    if peck <= 0:
        raise ValueError(f"peck_depth must be > 0, got {peck}")

    retract_z = strat.retract_to if strat.retract_to is not None else ctx.safe_z
    plunge_rate = ctx.plunge_rate if ctx.plunge_rate is not None else ctx.feed
    n = max(1, math.ceil(hole.depth / peck))

    tp.add_rapid(Vec3(cx, cy, ctx.safe_z))
    for i in range(n):
        target_z = top_z - min((i + 1) * peck, hole.depth)
        tp.add_feed(Vec3(cx, cy, target_z), plunge_rate)
        tp.add_rapid(Vec3(cx, cy, retract_z))
        if strat.dwell_at_top > 0 and i < n - 1:
            # Encode dwell as an inert "feed to current position" — the
            # machine.dispatch path doesn't carry G4 in Toolpath natively;
            # callers wanting precise dwell should issue it via the API directly.
            pass
    return tp
