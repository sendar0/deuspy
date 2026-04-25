"""Visualizer parser smoke tests — exercise the pure logic without Qt/VTK.

The full PyVistaBackend requires a running Qt event loop and is verified
manually. This test covers the line-to-event parser, which is where the
non-trivial logic actually lives.
"""

from __future__ import annotations

from deuspy.units import Vec3
from deuspy.viz.events import ToolMoveEvent
from deuspy.viz.pyvista_viewer import LineToEvent


def test_parser_absolute_g0():
    p = LineToEvent()
    ev = p.consume("G0 X1 Y2 Z3")
    assert isinstance(ev, ToolMoveEvent)
    assert ev.kind == "G0"
    assert ev.target == Vec3(1, 2, 3)
    assert p.position == Vec3(1, 2, 3)


def test_parser_absolute_g1_partial_axes_keeps_others():
    p = LineToEvent()
    p.consume("G0 X1 Y2 Z3")
    ev = p.consume("G1 X5 F100")
    assert ev is not None and ev.kind == "G1"
    assert ev.target == Vec3(5, 2, 3)


def test_parser_g91_relative_then_g90_absolute():
    p = LineToEvent()
    p.consume("G0 X10 Y10 Z0")
    p.consume("G91")
    ev = p.consume("G1 X1 Y2")
    assert ev is not None
    assert ev.target == Vec3(11, 12, 0)
    p.consume("G90")
    ev = p.consume("G0 X0 Y0 Z0")
    assert ev is not None and ev.target == Vec3(0, 0, 0)


def test_parser_ignores_non_motion():
    p = LineToEvent()
    assert p.consume("G21") is None
    assert p.consume("M3 S1000") is None
    assert p.consume("$H") is None


def test_parser_thread_safety_smoke():
    """Concurrent consume() calls don't crash. Doesn't prove correctness — just no exceptions."""
    import threading

    p = LineToEvent()

    def worker():
        for i in range(100):
            p.consume(f"G1 X{i} Y{i} Z0 F100")

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # Final position should be one of the (i, i, 0) end states.
    pos = p.position
    assert pos.x == pos.y
    assert pos.z == 0
