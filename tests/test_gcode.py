import pytest

from deuspy import gcode
from deuspy.units import CCW, CW, INCH, MM, Vec3


def test_rapid_full_axes():
    assert gcode.rapid(x=1, y=2, z=3) == "G0 X1 Y2 Z3"


def test_rapid_partial():
    assert gcode.rapid(x=1) == "G0 X1"
    assert gcode.rapid(z=-2.5) == "G0 Z-2.5"


def test_feed_with_f():
    assert gcode.feed(x=1, y=2, z=3, f=100) == "G1 X1 Y2 Z3 F100"


def test_feed_no_axes_just_f():
    # Useful for setting modal feed: pyserial expects something — we still emit G1.
    assert gcode.feed(f=100) == "G1 F100"


def test_units_gcode():
    assert gcode.units(MM) == "G21"
    assert gcode.units(INCH) == "G20"


def test_modes():
    assert gcode.absolute() == "G90"
    assert gcode.relative() == "G91"


def test_spindle_on_directions():
    assert gcode.spindle_on(1000, CW) == "M3 S1000"
    assert gcode.spindle_on(1000, CCW) == "M4 S1000"


def test_spindle_off():
    assert gcode.spindle_off() == "M5"


def test_home_full_axes():
    assert gcode.home("xyz") == "$H"


def test_home_partial_unsupported():
    with pytest.raises(ValueError):
        gcode.home("x")


def test_set_wcs_origin():
    assert gcode.set_wcs_origin(Vec3(0, 0, 0)) == "G10 L20 P1 X0 Y0 Z0"


def test_realtime_chars():
    assert gcode.feed_hold() == "!"
    assert gcode.cycle_resume() == "~"
    assert gcode.soft_reset() == "\x18"
    assert gcode.status_query() == "?"
    assert gcode.unlock() == "$X"


def test_number_formatting_strips_zeros():
    # 1.5000 → 1.5; 1.0 → 1; -0.0 → 0
    assert gcode.rapid(x=1.5) == "G0 X1.5"
    assert gcode.rapid(x=1.0) == "G0 X1"
    assert gcode.rapid(x=-0.0) == "G0 X0"


def test_select_wcs():
    assert gcode.select_wcs(1) == "G54"
    assert gcode.select_wcs(6) == "G59"
    with pytest.raises(ValueError):
        gcode.select_wcs(7)
