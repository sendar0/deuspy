"""G-code formatting helpers — pure string output, no I/O."""

from __future__ import annotations

from deuspy.units import SpindleDirection, Unit, Vec3


def _fmt(n: float) -> str:
    """Format a number with up to 4 decimals, no trailing zeros, no trailing dot."""
    s = f"{n:.4f}".rstrip("0").rstrip(".")
    return s if s and s != "-0" else "0"


def _axes(
    *,
    x: float | None = None,
    y: float | None = None,
    z: float | None = None,
    f: float | None = None,
) -> str:
    parts: list[str] = []
    if x is not None:
        parts.append(f"X{_fmt(x)}")
    if y is not None:
        parts.append(f"Y{_fmt(y)}")
    if z is not None:
        parts.append(f"Z{_fmt(z)}")
    if f is not None:
        parts.append(f"F{_fmt(f)}")
    return " ".join(parts)


def rapid(
    *,
    x: float | None = None,
    y: float | None = None,
    z: float | None = None,
) -> str:
    rest = _axes(x=x, y=y, z=z)
    return f"G0 {rest}".strip()


def feed(
    *,
    x: float | None = None,
    y: float | None = None,
    z: float | None = None,
    f: float | None = None,
) -> str:
    rest = _axes(x=x, y=y, z=z, f=f)
    return f"G1 {rest}".strip()


def units(unit: Unit) -> str:
    return unit.gcode


def absolute() -> str:
    return "G90"


def relative() -> str:
    return "G91"


def spindle_on(rpm: float, direction: SpindleDirection) -> str:
    return f"{direction.gcode} S{_fmt(rpm)}"


def spindle_off() -> str:
    return "M5"


def home(axes: str = "xyz") -> str:
    if axes.lower() == "xyz":
        return "$H"
    raise ValueError(f"Per-axis homing not supported in v1 (got {axes!r}); use 'xyz'.")


def set_wcs_origin(pos: Vec3, *, slot: int = 1) -> str:
    """G10 L20 P<slot> sets current position so it equals `pos` in the chosen WCS."""
    return f"G10 L20 P{slot} {_axes(x=pos.x, y=pos.y, z=pos.z)}".strip()


def select_wcs(slot: int = 1) -> str:
    """G54..G59 select a work coordinate system (slot 1..6)."""
    if not 1 <= slot <= 6:
        raise ValueError(f"WCS slot must be 1..6, got {slot}")
    return f"G5{3 + slot}"  # slot 1 -> G54, slot 6 -> G59


def unlock() -> str:
    return "$X"


def feed_hold() -> str:
    return "!"


def cycle_resume() -> str:
    return "~"


def soft_reset() -> str:
    return "\x18"


def status_query() -> str:
    return "?"
