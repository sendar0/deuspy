"""Cylinder, Hole, Polyline shapes + their strategies."""

from __future__ import annotations

import pytest

from deuspy.shapes import Cylinder, Hole, Polyline
from deuspy.strategies import Engrave, PeckDrill, Perimeter, Pocket
from deuspy.strategies.base import MachineContext
from deuspy.units import ORIGIN, Vec3


def make_ctx(*, tool=1.0, feed=100, safe_z=5.0):
    return MachineContext(
        position=ORIGIN,
        safe_z=safe_z,
        feed=feed,
        tool_diameter=tool,
    )


# --- Cylinder ----------------------------------------------------------------


def test_cylinder_bbox():
    cyl = Cylinder(radius=5, height=2, anchor=Vec3(10, 10, 0))
    lo, hi = cyl.bbox()
    assert lo == Vec3(5, 5, -2)
    assert hi == Vec3(15, 15, 0)


def test_cylinder_invalid_dims_raise():
    with pytest.raises(ValueError):
        Cylinder(radius=0, height=1)
    with pytest.raises(ValueError):
        Cylinder(radius=1, height=0)


def test_pocket_cylinder_emits_arcs():
    cyl = Cylinder(radius=5, height=1, anchor=ORIGIN)
    tp = Pocket(stepdown=0.5, stepover=0.5, finish_pass=False).plan(cyl, make_ctx(tool=1.0))
    arc_moves = [m for m in tp.moves if m.kind in ("G2", "G3")]
    assert len(arc_moves) > 0


def test_pocket_cylinder_too_small_for_tool():
    cyl = Cylinder(radius=0.5, height=1, anchor=ORIGIN)
    with pytest.raises(ValueError):
        Pocket().plan(cyl, make_ctx(tool=2.0))


def test_perimeter_cylinder_single_arc_per_layer():
    cyl = Cylinder(radius=5, height=2, anchor=ORIGIN)
    tp = Perimeter(stepdown=1.0).plan(cyl, make_ctx(tool=1.0))
    arc_moves = [m for m in tp.moves if m.kind in ("G2", "G3")]
    # Two depth levels → two arcs.
    assert len(arc_moves) == 2


def test_engrave_cylinder():
    cyl = Cylinder(radius=3, height=2, anchor=ORIGIN)
    tp = Engrave(depth=0.2).plan(cyl, make_ctx(tool=1.0))
    arc_moves = [m for m in tp.moves if m.kind in ("G2", "G3")]
    assert len(arc_moves) == 1


# --- Hole / PeckDrill --------------------------------------------------------


def test_hole_bbox_and_radius():
    h = Hole(diameter=4, depth=10, anchor=ORIGIN)
    assert h.radius == 2
    lo, hi = h.bbox()
    assert lo == Vec3(-2, -2, -10)
    assert hi == Vec3(2, 2, 0)


def test_peck_drill_progresses_in_increments():
    h = Hole(diameter=4, depth=5, anchor=ORIGIN)
    tp = PeckDrill(peck_depth=2.0).plan(h, make_ctx(tool=2.0, safe_z=5))
    plunges = [m for m in tp.moves if m.kind == "G1"]
    # 5 / 2 = 2.5 → 3 pecks at -2, -4, -5.
    targets = [m.target.z for m in plunges]
    assert targets == [-2.0, -4.0, -5.0]


def test_peck_drill_tool_too_big_raises():
    h = Hole(diameter=2, depth=5)
    with pytest.raises(ValueError):
        PeckDrill().plan(h, make_ctx(tool=3.0))


def test_peck_drill_only_supports_holes():
    cyl = Cylinder(radius=5, height=1)
    with pytest.raises(NotImplementedError):
        PeckDrill().plan(cyl, make_ctx())


# --- Polyline ----------------------------------------------------------------


def test_polyline_requires_two_points():
    with pytest.raises(ValueError):
        Polyline(points=[Vec3(0, 0, 0)], depth=1)


def test_polyline_bbox():
    poly = Polyline(
        points=[Vec3(0, 0, 0), Vec3(10, 5, 0), Vec3(0, 5, 0)],
        depth=2,
    )
    lo, hi = poly.bbox()
    assert lo == Vec3(0, 0, -2)
    assert hi == Vec3(10, 5, 0)


def test_polyline_rectangle_factory():
    poly = Polyline.rectangle(length=4, width=2, depth=1)
    assert len(poly.points) == 4
    assert poly.closed is True


def test_perimeter_polyline_emits_segments():
    poly = Polyline.rectangle(length=10, width=10, depth=2)
    tp = Perimeter(stepdown=1.0, offset=0).plan(poly, make_ctx(tool=1.0))
    feeds = [m for m in tp.moves if m.kind == "G1"]
    # Per layer: 1 plunge + 4 outline segments. Two layers → 10 G1 moves.
    assert len(feeds) == 10


def test_perimeter_polyline_offset_unsupported():
    poly = Polyline.rectangle(length=10, width=10, depth=1)
    with pytest.raises(NotImplementedError):
        Perimeter(offset=1.0).plan(poly, make_ctx(tool=1.0))


def test_engrave_polyline():
    poly = Polyline.rectangle(length=10, width=10, depth=1)
    tp = Engrave(depth=0.3).plan(poly, make_ctx(tool=1.0))
    feeds = [m for m in tp.moves if m.kind == "G1"]
    # 1 plunge + 4 outline = 5 G1 moves.
    assert len(feeds) == 5
