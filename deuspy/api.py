"""Functional facade over the Machine singleton — what users call from the REPL."""

from __future__ import annotations

import logging

from deuspy import config, gcode
from deuspy.backends.base import MachineStatus
from deuspy.backends.dryrun import DryRunBackend
from deuspy.machine import MachineState, Tool, get_machine, reset_machine
from deuspy.shapes.base import Shape
from deuspy.strategies.base import Strategy
from deuspy.toolpath import Toolpath
from deuspy.units import CW, ORIGIN, SpindleDirection, Unit, Vec3

log = logging.getLogger("deuspy")


def connect(
    port: str | None = None,
    *,
    baud: int = config.DEFAULT_BAUD,
    dry_run: bool = False,
    visualize: bool = True,
) -> None:
    """Connect to the CNC controller.

    port:      Serial device. If None, autodetects a likely GRBL port.
    dry_run:   If True, skip hardware and use a DryRunBackend as authoritative.
    visualize: If True, attach the PyVista visualizer as a non-authoritative backend.
    """
    m = get_machine()
    if m.backends:
        raise RuntimeError("Already connected. Call disconnect() first.")

    if dry_run or port is None and _no_serial_available():
        backend = DryRunBackend()
        m.add_backend(backend)
    else:
        from deuspy.backends.grbl import GrblBackend  # local import — pyserial only required here
        grbl = GrblBackend(port=port, baud=baud)
        grbl.open()
        m.add_backend(grbl)

    if visualize:
        try:
            from deuspy.viz.pyvista_viewer import PyVistaBackend
            viz = PyVistaBackend()
            m.add_backend(viz)
        except Exception as exc:  # noqa: BLE001
            log.warning("Visualizer disabled: %s", exc)

    # Push the machine's current modal state so the controller agrees with us.
    m.dispatch(gcode.units(m.units))
    m.dispatch(gcode.absolute())
    m.state = MachineState.READY


def disconnect() -> None:
    reset_machine()


def _no_serial_available() -> bool:
    """Best-effort check: is there any serial port we can plausibly use?"""
    try:
        from serial.tools import list_ports
        return not list(list_ports.comports())
    except Exception:  # noqa: BLE001
        return True


def move(
    target: Vec3 | str = "current",
    *,
    x: float | None = None,
    y: float | None = None,
    z: float | None = None,
    rapid: bool = False,
    relative: bool = False,
    blocking: bool = True,
) -> None:
    """Move the head. `target` may be a Vec3 or the string 'origin'/'current'.

    Without a target Vec3, supplying only x/y/z keeps the other axes at their current
    value — the manual-machine convention. To lift the head, pass z= explicitly.
    """
    get_machine().move(
        target,
        x=x,
        y=y,
        z=z,
        rapid=rapid,
        relative=relative,
        blocking=blocking,
    )


def set_units(unit: Unit) -> None:
    get_machine().set_units(unit)


def set_movement_speed(feed: float) -> None:
    """Set the feed rate for subsequent G1 moves (current units / minute)."""
    get_machine().set_feed(feed)


def set_spindle_speed(rpm: float, *, direction: SpindleDirection = CW) -> None:
    """Set spindle RPM. rpm=0 turns the spindle off."""
    get_machine().set_spindle(rpm, direction)


def home(axes: str = "xyz") -> None:
    get_machine().home(axes)


def set_origin(pos: Vec3 = ORIGIN) -> None:
    """Tell the controller the current machine position equals `pos` in the active WCS."""
    get_machine().set_origin(pos)


def set_safe_z(z: float) -> None:
    get_machine().set_safe_z(z)


def set_tool(tool: Tool) -> None:
    get_machine().set_tool(tool)


def set_stock(size: Vec3, anchor: Vec3 = ORIGIN) -> None:
    get_machine().set_stock(size, anchor)


def execute(
    op: Shape,
    strategy: Strategy | None = None,
    *,
    blocking: bool = True,
    preview: bool = False,
) -> Toolpath:
    """Generate and run a toolpath for `op`.

    If strategy is None, defaults to a Pocket strategy. preview=True returns the
    Toolpath without sending it.
    """
    return get_machine().execute(op, strategy, blocking=blocking, preview=preview)


def stop(*, soft: bool = True) -> None:
    """Halt motion. soft=True is a feed-hold; soft=False is a full reset."""
    get_machine().stop(soft=soft)


def status() -> MachineStatus:
    return get_machine().status()


def unlock() -> None:
    """Clear an alarm state ($X). The user must call this explicitly after an alarm."""
    get_machine().dispatch(gcode.unlock())
    get_machine().state = MachineState.READY
