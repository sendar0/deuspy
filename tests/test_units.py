import pytest

from deuspy.units import INCH, MM, ORIGIN, Vec3, convert, convert_vec


def test_vec3_arithmetic():
    a = Vec3(1, 2, 3)
    b = Vec3(0.5, -1, 2)
    assert a + b == Vec3(1.5, 1, 5)
    assert a - b == Vec3(0.5, 3, 1)
    assert a * 2 == Vec3(2, 4, 6)
    assert 2 * a == Vec3(2, 4, 6)


def test_vec3_with_partial_update():
    v = Vec3(1, 2, 3)
    assert v.with_(x=10) == Vec3(10, 2, 3)
    assert v.with_(y=20, z=30) == Vec3(1, 20, 30)
    assert v.with_() == v


def test_origin_is_zero():
    assert Vec3(0, 0, 0) == ORIGIN


def test_unit_gcode():
    assert MM.gcode == "G21"
    assert INCH.gcode == "G20"


def test_convert_scalar():
    assert convert(1.0, INCH, MM) == 25.4
    assert convert(25.4, MM, INCH) == 1.0
    assert convert(5.0, MM, MM) == 5.0


def test_convert_vec():
    v = convert_vec(Vec3(1, 2, 3), INCH, MM)
    assert v.x == pytest.approx(25.4)
    assert v.y == pytest.approx(50.8)
    assert v.z == pytest.approx(76.2)
