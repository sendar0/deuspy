"""Multi-WCS, tool change, probe."""

from __future__ import annotations

import io

import pytest

from deuspy import (
    MM,
    Tool,
    change_tool,
    connect,
    disconnect,
    probe,
    select_wcs,
    set_origin,
    set_tool,
    set_units,
)
from deuspy.backends.dryrun import DryRunBackend
from deuspy.machine import get_machine
from deuspy.units import Vec3


def _swap_in_capture():
    m = get_machine()
    m.backends.clear()
    backend = DryRunBackend(stream=io.StringIO(), echo=False)
    m.add_backend(backend)
    return backend


# --- Multi-WCS ---------------------------------------------------------------


def test_default_wcs_slot_is_one():
    connect(dry_run=True, visualize=False)
    assert get_machine().wcs_slot == 1
    disconnect()


def test_set_origin_with_explicit_slot_emits_g10_and_g_select():
    connect(dry_run=True, visualize=False)
    backend = _swap_in_capture()
    set_origin(Vec3(0, 0, 0), slot=3)
    # G10 L20 P3 sets the origin, then G56 activates slot 3.
    assert any("G10 L20 P3" in line for line in backend.lines)
    assert any(line == "G56" for line in backend.lines)
    assert get_machine().wcs_slot == 3
    disconnect()


def test_set_origin_default_slot_uses_active_wcs():
    connect(dry_run=True, visualize=False)
    select_wcs(2)
    backend = _swap_in_capture()
    set_origin(Vec3(0, 0, 0))
    # Should have used slot 2 (the active one), no slot switch.
    assert any("G10 L20 P2" in line for line in backend.lines)
    assert not any(line.startswith("G55") for line in backend.lines), (
        "no extra select required when slot already active"
    )
    disconnect()


def test_select_wcs_emits_correct_gcode():
    connect(dry_run=True, visualize=False)
    backend = _swap_in_capture()
    for slot, expected in [(1, "G54"), (2, "G55"), (3, "G56"), (6, "G59")]:
        select_wcs(slot)
        assert expected in backend.lines
    disconnect()


def test_select_wcs_invalid_slot():
    connect(dry_run=True, visualize=False)
    with pytest.raises(ValueError):
        select_wcs(7)
    with pytest.raises(ValueError):
        select_wcs(0)
    disconnect()


# --- Tool change -------------------------------------------------------------


def test_change_tool_stops_spindle_retracts_and_updates_tool(monkeypatch):
    connect(dry_run=True, visualize=False)
    set_units(MM)
    set_tool(Tool(diameter=3.0, name="3mm endmill"))
    backend = _swap_in_capture()

    # Disable the input() prompt so the test is non-interactive.
    monkeypatch.setattr("builtins.input", lambda *_a, **_kw: "")

    change_tool(Tool(diameter=6.0, name="6mm flat"))
    assert "M5" in backend.lines, "spindle should be stopped before changing"
    assert any(line.startswith("G0 Z") for line in backend.lines), "should retract Z"
    assert get_machine().tool.diameter == 6.0
    assert get_machine().spindle_rpm == 0.0
    disconnect()


def test_change_tool_with_m6_emits_m6(monkeypatch):
    connect(dry_run=True, visualize=False)
    set_units(MM)
    backend = _swap_in_capture()
    monkeypatch.setattr("builtins.input", lambda *_a, **_kw: "")
    change_tool(Tool(diameter=4.0), m6=True)
    assert any(line.startswith("M6 T") for line in backend.lines)
    disconnect()


# --- Probe -------------------------------------------------------------------


def test_probe_emits_g38_2_in_correct_direction():
    connect(dry_run=True, visualize=False)
    set_units(MM)
    backend = _swap_in_capture()
    line = probe(direction="Z-", max_distance=10, feed=50)
    assert line.startswith("G38.2")
    assert "Z-10" in line
    assert "F50" in line
    assert backend.lines[-1] == line
    disconnect()


def test_probe_with_no_contact_uses_g38_3():
    connect(dry_run=True, visualize=False)
    line = probe(direction="X+", max_distance=5, feed=20, error_on_no_contact=False)
    assert line.startswith("G38.3")
    assert "X5" in line
    disconnect()


def test_probe_invalid_direction():
    connect(dry_run=True, visualize=False)
    with pytest.raises(ValueError):
        probe(direction="W+", max_distance=10)
    with pytest.raises(ValueError):
        probe(direction="Z-", max_distance=0)
    disconnect()
