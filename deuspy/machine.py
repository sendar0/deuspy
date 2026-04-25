"""Machine: state holder + dispatch core that the functional API operates on."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from deuspy import config, gcode
from deuspy.backends.base import Backend, MachineStatus
from deuspy.errors import AlarmError, CncError, NotConnectedError
from deuspy.shapes.base import Shape
from deuspy.strategies.base import MachineContext, Strategy
from deuspy.toolpath import Toolpath
from deuspy.units import CW, ORIGIN, SpindleDirection, Unit, Vec3

log = logging.getLogger("deuspy")


class MachineState(Enum):
    DISCONNECTED = "disconnected"
    READY = "ready"
    BUSY = "busy"
    HALTED = "halted"


@dataclass
class Tool:
    diameter: float = config.DEFAULT_TOOL_DIAMETER
    flutes: int = config.DEFAULT_TOOL_FLUTES
    plunge_rate: float | None = None
    name: str = ""


@dataclass
class Stock:
    size: Vec3
    anchor: Vec3 = ORIGIN


@dataclass
class Machine:
    """Singleton-style state holder. Use the functions in `deuspy.api` from a REPL."""

    units: Unit = Unit.MM
    feed: float = config.DEFAULT_FEED
    spindle_rpm: float = 0.0
    spindle_direction: SpindleDirection = CW
    position: Vec3 = ORIGIN
    safe_z: float = config.DEFAULT_SAFE_Z
    tool: Tool = field(default_factory=Tool)
    stock: Stock | None = None
    state: MachineState = MachineState.DISCONNECTED
    backends: list[Backend] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Backend management
    # ------------------------------------------------------------------

    def add_backend(self, backend: Backend) -> None:
        if backend.is_authoritative() and any(b.is_authoritative() for b in self.backends):
            raise CncError("Multiple authoritative backends registered. Disconnect first.")
        self.backends.append(backend)

    def authoritative(self) -> Backend:
        for b in self.backends:
            if b.is_authoritative():
                return b
        raise NotConnectedError("No authoritative backend. Call connect() first.")

    def close_all(self) -> None:
        for b in self.backends:
            try:
                b.close()
            except Exception as exc:  # noqa: BLE001 — backend cleanup must be best-effort
                log.warning("Backend %s close raised: %s", b.name, exc)
        self.backends.clear()
        self.state = MachineState.DISCONNECTED

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def dispatch(self, line: str, *, blocking: bool = True) -> None:
        """Send one G-code line: authoritative first, then fan out best-effort."""
        if not line:
            return
        primary = self.authoritative()
        try:
            result = primary.send(line, blocking=blocking)
        except KeyboardInterrupt:
            # User hit Ctrl-C in a blocking move: feed-hold immediately, then re-raise.
            self._emergency_hold(primary)
            raise
        if not result.ok:
            self.state = MachineState.HALTED
            raise AlarmError(result.error_code, result.raw or f"backend {primary.name} rejected line")

        for b in self.backends:
            if b is primary:
                continue
            try:
                b.send(line, blocking=False)
            except Exception as exc:  # noqa: BLE001
                log.warning("Non-authoritative backend %s failed on %r: %s", b.name, line, exc)

        # Refresh position from the authoritative backend after motion.
        if blocking and line.split(maxsplit=1)[0] in ("G0", "G1"):
            try:
                st = primary.status()
                self.position = st.wpos
            except Exception as exc:  # noqa: BLE001
                log.debug("Status refresh failed after %r: %s", line, exc)

    def _emergency_hold(self, primary: Backend) -> None:
        try:
            primary.stop(soft=True)
        except Exception as exc:  # noqa: BLE001
            log.error("Feed-hold failed: %s", exc)
        self.state = MachineState.HALTED

    # ------------------------------------------------------------------
    # High-level operations
    # ------------------------------------------------------------------

    def set_units(self, unit: Unit) -> None:
        self.units = unit
        self.dispatch(gcode.units(unit))

    def set_feed(self, feed: float) -> None:
        if feed <= 0:
            raise ValueError(f"feed must be > 0, got {feed}")
        self.feed = feed
        # Feed is sticky: emit a feed-only G1 word so GRBL caches it modally.
        self.dispatch(f"G1 F{feed:g}")

    def set_spindle(self, rpm: float, direction: SpindleDirection = CW) -> None:
        if rpm < 0:
            raise ValueError(f"rpm must be >= 0, got {rpm}")
        self.spindle_rpm = rpm
        self.spindle_direction = direction
        if rpm == 0:
            self.dispatch(gcode.spindle_off())
        else:
            self.dispatch(gcode.spindle_on(rpm, direction))

    def home(self, axes: str = "xyz") -> None:
        self.dispatch(gcode.home(axes))
        self.position = ORIGIN  # post-home machine zero — true work pos refreshed by status poll

    def set_origin(self, pos: Vec3 = ORIGIN) -> None:
        """Make the current machine position equal `pos` in the current WCS (G54)."""
        self.dispatch(gcode.set_wcs_origin(pos, slot=1))
        self.position = pos

    def set_safe_z(self, z: float) -> None:
        self.safe_z = z

    def set_tool(self, tool: Tool) -> None:
        if tool.diameter <= 0:
            raise ValueError(f"tool.diameter must be > 0, got {tool.diameter}")
        self.tool = tool

    def set_stock(self, size: Vec3, anchor: Vec3 = ORIGIN) -> None:
        self.stock = Stock(size=size, anchor=anchor)
        # Notify visualizer-style backends; ignored by hardware.
        for b in self.backends:
            update = getattr(b, "update_stock", None)
            if update is not None:
                try:
                    update(self.stock)
                except Exception as exc:  # noqa: BLE001
                    log.warning("Backend %s update_stock failed: %s", b.name, exc)

    def move(
        self,
        target: Vec3 | str = "current",
        *,
        x: float | None = None,
        y: float | None = None,
        z: float | None = None,
        rapid: bool = False,
        relative: bool = False,
        blocking: bool = True,
    ) -> None:
        # Resolve target to a Vec3 in the current WCS.
        resolved = self._resolve_target(target, x=x, y=y, z=z, relative=relative)

        if relative:
            self.dispatch(gcode.relative())

        if rapid:
            line = gcode.rapid(x=resolved.x, y=resolved.y, z=resolved.z)
        else:
            line = gcode.feed(x=resolved.x, y=resolved.y, z=resolved.z, f=self.feed)

        try:
            self.dispatch(line, blocking=blocking)
        finally:
            if relative:
                # Always restore absolute mode so subsequent commands behave predictably.
                self.dispatch(gcode.absolute())

        if not relative:
            self.position = resolved
        else:
            self.position = self.position + resolved

    def _resolve_target(
        self,
        target: Vec3 | str,
        *,
        x: float | None,
        y: float | None,
        z: float | None,
        relative: bool,
    ) -> Vec3:
        if isinstance(target, str):
            if target == "origin":
                base = ORIGIN
            elif target == "current":
                base = self.position if not relative else ORIGIN
            else:
                raise ValueError(f"Unknown target string {target!r}; expected 'origin' or 'current'")
        elif isinstance(target, Vec3):
            base = target
        else:
            raise TypeError(f"target must be Vec3 or 'origin'/'current', got {type(target).__name__}")

        return base.with_(x=x, y=y, z=z)

    def execute(
        self,
        op: Shape,
        strategy: Strategy | None = None,
        *,
        blocking: bool = True,
        preview: bool = False,
    ) -> Toolpath:
        if strategy is None:
            from deuspy.strategies import Pocket
            strategy = Pocket()

        ctx = MachineContext(
            position=self.position,
            safe_z=self.safe_z,
            feed=self.feed,
            tool_diameter=self.tool.diameter,
            plunge_rate=self.tool.plunge_rate,
        )
        tp = strategy.plan(op, ctx)

        if preview:
            return tp

        for line in tp.iter_gcode():
            self.dispatch(line, blocking=blocking)

        # After execute(), retract to safe Z so the user is at a known clearance.
        retract_line = gcode.rapid(z=self.safe_z)
        self.dispatch(retract_line, blocking=blocking)
        return tp

    def stop(self, *, soft: bool = True) -> None:
        primary = self.authoritative()
        primary.stop(soft=soft)
        self.state = MachineState.HALTED

    def status(self) -> MachineStatus:
        return self.authoritative().status()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_machine: Machine | None = None


def get_machine() -> Machine:
    global _machine
    if _machine is None:
        _machine = Machine()
    return _machine


def reset_machine() -> None:
    """Test helper: tear down the singleton."""
    global _machine
    if _machine is not None:
        _machine.close_all()
    _machine = None
