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
    wcs_slot: int = 1  # 1..6 → G54..G59

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
        if blocking and line.split(maxsplit=1)[0] in ("G0", "G1", "G2", "G3"):
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

    def set_origin(self, pos: Vec3 = ORIGIN, *, slot: int | None = None) -> None:
        """Make the current machine position equal `pos` in a WCS slot (default = active).

        slot=None uses the currently selected WCS. slot=1..6 maps to G54..G59.
        """
        target_slot = self.wcs_slot if slot is None else slot
        if not 1 <= target_slot <= 6:
            raise ValueError(f"WCS slot must be 1..6, got {target_slot}")
        self.dispatch(gcode.set_wcs_origin(pos, slot=target_slot))
        if slot is not None and slot != self.wcs_slot:
            self.dispatch(gcode.select_wcs(slot))
            self.wcs_slot = slot
        self.position = pos

    def select_wcs(self, slot: int) -> None:
        """Activate work coordinate system slot 1..6 (G54..G59)."""
        if not 1 <= slot <= 6:
            raise ValueError(f"WCS slot must be 1..6, got {slot}")
        self.dispatch(gcode.select_wcs(slot))
        self.wcs_slot = slot

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
    ):
        """Plan and run a toolpath for `op`.

        blocking=True (default): each line is sent + acked synchronously, prompt waits.
                                 Returns the planned Toolpath.
        blocking=False:          streams the toolpath through the backend's character-
                                 counting streamer in a background thread. Returns a
                                 (Toolpath, Job) tuple. Caller can wait()/cancel() the Job.
        preview=True:            returns the Toolpath without sending.
        """
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

        retract_line = gcode.rapid(z=self.safe_z)

        if blocking:
            for line in tp.iter_gcode():
                self.dispatch(line, blocking=True)
            self.dispatch(retract_line, blocking=True)
            return tp

        # Streaming mode: hand the whole toolpath (plus retract) to the backend.
        from deuspy.job import Job
        primary = self.authoritative()
        stream_fn = getattr(primary, "stream", None)
        if stream_fn is None:
            raise NotConnectedError(
                f"Backend {primary.name} does not support streaming. "
                "Use blocking=True or switch to GRBL/DryRun."
            )
        all_lines = list(tp.iter_gcode()) + [retract_line]
        job = Job()
        stream_fn(all_lines, job)
        # Best-effort: also tee the lines to non-authoritative backends. They're
        # synchronous (visualizer queues events; DryRun appends), so this is fine
        # to do on the calling thread.
        for b in self.backends:
            if b is primary:
                continue
            for line in all_lines:
                try:
                    b.send(line, blocking=False)
                except Exception as exc:  # noqa: BLE001
                    log.warning("Non-authoritative backend %s failed during stream: %s", b.name, exc)
        return tp, job

    def stop(self, *, soft: bool = True) -> None:
        primary = self.authoritative()
        primary.stop(soft=soft)
        self.state = MachineState.HALTED

    def status(self) -> MachineStatus:
        return self.authoritative().status()

    def change_tool(self, tool: Tool, *, m6: bool = False, prompt: bool = True) -> None:
        """Pause for a manual tool change, then continue with the new tool.

        Stops the spindle, retracts to safe Z, optionally emits M6 (machine-specific),
        prompts the user via input() if `prompt`, and stores the new tool.
        Spindle is left off — restart with `set_spindle_speed(rpm)` after the swap.
        """
        if tool.diameter <= 0:
            raise ValueError(f"tool.diameter must be > 0, got {tool.diameter}")
        # Halt cutting safely.
        self.dispatch(gcode.spindle_off())
        self.dispatch(gcode.rapid(z=self.safe_z))
        if m6:
            # M6 support varies by GRBL fork; many builds reject it. Caller opts in.
            tool_number = max(1, getattr(tool, "number", 1))
            self.dispatch(gcode.tool_change(tool_number))
        log.info("Tool change requested: %s (diameter=%.3f)", tool.name or "unnamed", tool.diameter)
        if prompt:
            try:
                input(f"Tool change: install {tool.name or 'tool'} (Ø{tool.diameter}). Press Enter when ready... ")
            except EOFError:
                # No interactive prompt available (tests, scripts) — proceed silently.
                log.warning("No TTY for tool-change prompt; proceeding immediately.")
        self.tool = tool
        self.spindle_rpm = 0.0  # caller must restart the spindle

    def probe(
        self,
        *,
        direction: str = "Z-",
        max_distance: float,
        feed: float = 50.0,
        error_on_no_contact: bool = True,
    ) -> str:
        """Issue a G38.2 probing move toward `direction` for up to `max_distance`.

        direction: one of 'X+','X-','Y+','Y-','Z+','Z-'.
        Returns the raw G-code line emitted; the caller is responsible for reading
        the controller's `[PRB:x,y,z:N]` response (parsing varies by GRBL fork and
        is not done by deuspy in v2).
        """
        if direction not in {"X+", "X-", "Y+", "Y-", "Z+", "Z-"}:
            raise ValueError(f"direction must be one of X±/Y±/Z±, got {direction!r}")
        if max_distance <= 0:
            raise ValueError(f"max_distance must be > 0, got {max_distance}")
        axis = direction[0].lower()
        sign = 1.0 if direction[1] == "+" else -1.0
        delta = sign * max_distance
        target = self.position.with_(**{axis: getattr(self.position, axis) + delta})
        line = gcode.probe_toward(
            x=target.x if axis == "x" else None,
            y=target.y if axis == "y" else None,
            z=target.z if axis == "z" else None,
            f=feed,
            error_on_no_contact=error_on_no_contact,
        )
        log.warning(
            "probe(): emitting %s; PRB response parsing is not implemented in v2 — "
            "read the serial transcript or upgrade in v3.", line,
        )
        self.dispatch(line)
        return line


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
