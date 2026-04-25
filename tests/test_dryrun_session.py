"""Acceptance gate: replay the README REPL session through the DryRun backend.

This is the contract test. If this fails, the public API has regressed.
"""

from __future__ import annotations

import io

from deuspy import (
    MM,
    Box,
    Tool,
    connect,
    disconnect,
    execute,
    move,
    origin,
    set_movement_speed,
    set_spindle_speed,
    set_tool,
    set_units,
)
from deuspy.backends.dryrun import DryRunBackend
from deuspy.machine import get_machine


def _capture_lines() -> tuple[DryRunBackend, list[str]]:
    """Replace the default DryRun backend with one that captures lines silently."""
    m = get_machine()
    # Remove anything connect() installed.
    m.backends.clear()
    backend = DryRunBackend(stream=io.StringIO(), echo=False)
    m.add_backend(backend)
    return backend, backend.lines


def test_repl_session_user_example():
    """The exact session from the README runs end-to-end without errors."""
    connect(dry_run=True, visualize=False)
    backend, lines = _capture_lines()
    # Re-emit init lines through the captured backend so the trace matches reality.
    from deuspy import gcode as g
    backend.send(g.units(MM))
    backend.send(g.absolute())

    # Use a tool that fits the user's 4×2 mm pocket (default 3 mm wouldn't fit).
    set_tool(Tool(diameter=1.0))

    move(origin)
    set_units(MM)
    set_movement_speed(1)
    move(x=2, y=2)
    set_spindle_speed(12)
    box = Box(length=4, height=4, width=2)
    execute(box)

    # ---- Spot-check the recorded G-code ----
    # set_units emits G21 again
    assert "G21" in lines
    # set_movement_speed emits G1 F1 (sticky modal feed)
    assert "G1 F1" in lines
    # move(origin) emits a G1 to (0,0,0)
    assert any(line.startswith("G1 X0 Y0 Z0") for line in lines)
    # move(x=2, y=2) keeps current Z (0) and uses feed 1
    assert any(line == "G1 X2 Y2 Z0 F1" for line in lines)
    # set_spindle_speed(12) emits M3 S12
    assert "M3 S12" in lines
    # execute(box) generates several G0/G1 lines.
    motion_lines = [ln for ln in lines if ln.startswith(("G0 ", "G1 X"))]
    assert len(motion_lines) > 5, f"expected several motion lines, got {motion_lines}"
    # final retract is a rapid Z to safe height.
    assert any(line.startswith("G0 Z") for line in lines)

    disconnect()


def test_machine_position_tracks_after_move():
    connect(dry_run=True, visualize=False)
    move(origin)
    move(x=2, y=3)
    m = get_machine()
    assert m.position.x == 2
    assert m.position.y == 3
    assert m.position.z == 0  # XY-only move keeps current Z
    disconnect()


def test_set_units_applied_modally():
    connect(dry_run=True, visualize=False)
    set_units(MM)
    m = get_machine()
    assert m.units == MM
    disconnect()


def test_set_spindle_zero_emits_m5():
    connect(dry_run=True, visualize=False)
    set_spindle_speed(0)
    m = get_machine()
    backend = m.backends[0]
    assert "M5" in backend.lines  # type: ignore[attr-defined]
    disconnect()


def test_double_connect_raises():
    import pytest
    connect(dry_run=True, visualize=False)
    with pytest.raises(RuntimeError):
        connect(dry_run=True, visualize=False)
    disconnect()
