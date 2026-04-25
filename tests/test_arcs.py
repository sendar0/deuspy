"""Arcs: gcode emission, Move dataclass, parser updates."""

from __future__ import annotations

import pytest

from deuspy import gcode
from deuspy.toolpath import Move, Toolpath
from deuspy.units import Vec3


def test_arc_cw_emits_g2():
    line = gcode.arc(x=10, y=0, i=-5, j=0, f=100, clockwise=True)
    assert line == "G2 X10 Y0 I-5 J0 F100"


def test_arc_ccw_emits_g3():
    line = gcode.arc(x=10, y=0, i=-5, j=0, f=100, clockwise=False)
    assert line == "G3 X10 Y0 I-5 J0 F100"


def test_arc_with_z_helix():
    line = gcode.arc(x=5, y=5, z=-2, i=-5, j=0, f=50, clockwise=True)
    assert line == "G2 X5 Y5 Z-2 I-5 J0 F50"


def test_move_arc_to_gcode():
    m = Move("G2", Vec3(10, 0, 0), feed=100, center_offset=Vec3(-5, 0, 0))
    assert m.to_gcode() == "G2 X10 Y0 Z0 I-5 J0 K0 F100"


def test_move_arc_without_center_offset_raises():
    m = Move("G2", Vec3(10, 0, 0), feed=100, center_offset=None)
    with pytest.raises(ValueError):
        m.to_gcode()


def test_toolpath_add_arc():
    tp = Toolpath()
    tp.add_arc(Vec3(10, 0, 0), center_offset=Vec3(-5, 0, 0), clockwise=True, feed=100)
    assert len(tp) == 1
    assert tp.moves[0].kind == "G2"
    assert tp.moves[0].center_offset == Vec3(-5, 0, 0)


def test_dryrun_tracks_position_through_arc():
    from deuspy.backends.dryrun import DryRunBackend
    b = DryRunBackend(echo=False)
    b.send("G90")
    b.send("G0 X10 Y0 Z0")
    b.send("G2 X0 Y0 I-5 J0 F100")
    # Arc lands at (0, 0, 0).
    assert b.status().wpos == Vec3(0, 0, 0)


def test_visualizer_parser_handles_arcs():
    from deuspy.viz.pyvista_viewer import LineToEvent
    p = LineToEvent()
    p.consume("G0 X10 Y0 Z0")
    ev = p.consume("G2 X0 Y0 I-5 J0 F100")
    assert ev is not None
    assert ev.kind == "G2"
    assert ev.target == Vec3(0, 0, 0)


def test_plane_helpers():
    assert gcode.plane_xy() == "G17"
    assert gcode.plane_xz() == "G18"
    assert gcode.plane_yz() == "G19"


def test_dwell():
    assert gcode.dwell(0.5) == "G4 P0.5"


def test_tool_change():
    assert gcode.tool_change(3) == "M6 T3"
    with pytest.raises(ValueError):
        gcode.tool_change(0)


def test_probe_toward():
    assert gcode.probe_toward(z=-10, f=50) == "G38.2 Z-10 F50"
    assert gcode.probe_toward(z=-10, f=50, error_on_no_contact=False) == "G38.3 Z-10 F50"
