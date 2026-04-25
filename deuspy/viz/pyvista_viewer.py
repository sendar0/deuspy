"""PyVista visualizer backend.

The visualizer is a non-authoritative Backend: it observes G-code as it's dispatched
and renders the cumulative toolpath, current tool position, and stock outline.

Threading contract
------------------
Backend.send() is called on the REPL thread. VTK / pyvista calls must happen on
the Qt GUI thread. We bridge with a thread-safe queue: send() enqueues a VizEvent,
a Qt timer drains the queue on the GUI thread.

For testability, the line-parsing logic lives in `LineToEvent` (pure, no Qt/VTK).
"""

from __future__ import annotations

import logging
import queue
import re
import threading
from typing import TYPE_CHECKING

from deuspy.backends.base import BackendResult, MachineStatus
from deuspy.units import ORIGIN, Vec3
from deuspy.viz.events import AlarmEvent, ClearEvent, StockEvent, ToolMoveEvent, VizEvent

log = logging.getLogger("deuspy.viz")

_AXIS_RE = re.compile(r"([XYZ])([-+]?\d*\.?\d+)")

if TYPE_CHECKING:
    from deuspy.machine import Stock


class LineToEvent:
    """Pure line-to-event parser. No VTK, no Qt — testable in isolation."""

    def __init__(self) -> None:
        self.position = ORIGIN
        self.absolute = True
        self._lock = threading.Lock()

    def consume(self, line: str) -> VizEvent | None:
        head = line.split(maxsplit=1)[0] if line else ""
        if head == "G90":
            with self._lock:
                self.absolute = True
            return None
        if head == "G91":
            with self._lock:
                self.absolute = False
            return None
        if head not in ("G0", "G1"):
            return None

        x = y = z = None
        for axis, val in _AXIS_RE.findall(line):
            v = float(val)
            if axis == "X":
                x = v
            elif axis == "Y":
                y = v
            elif axis == "Z":
                z = v

        with self._lock:
            if self.absolute:
                self.position = self.position.with_(x=x, y=y, z=z)
            else:
                self.position = Vec3(
                    self.position.x + (x or 0.0),
                    self.position.y + (y or 0.0),
                    self.position.z + (z or 0.0),
                )
            target = self.position
        return ToolMoveEvent(target=target, kind="G0" if head == "G0" else "G1")


class PyVistaBackend:
    """Live 3D + top-down toolpath viewer.

    Renders:
      - Translucent stock outline (if Machine.set_stock(...) was called)
      - Rapid moves (G0) as dashed grey segments
      - Feed moves (G1) as solid blue segments
      - Tool tip sphere at the current position
    """

    name = "pyvista"

    def __init__(self, *, off_screen: bool | None = None) -> None:
        # Lazy import — pyvista/pyvistaqt are optional extras.
        try:
            import pyvista as pv
            from pyvistaqt import BackgroundPlotter
        except ImportError as exc:
            raise RuntimeError(
                "pyvista and pyvistaqt are required for visualization. "
                "Install with: pip install 'deuspy[viz]'"
            ) from exc

        self._pv = pv
        if off_screen is not None:
            pv.OFF_SCREEN = off_screen  # type: ignore[attr-defined]

        self._events: queue.Queue[VizEvent] = queue.Queue()
        self._parser = LineToEvent()

        self._plotter = BackgroundPlotter(
            shape=(1, 2),
            window_size=(1200, 600),
            title="deuspy — toolpath",
            update_app_icon=False,
        )
        self._setup_views()
        self._tool_actor = None
        self._stock_actor = None
        self._plotter.add_callback(self._drain_queue, interval=50)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_views(self) -> None:
        pv = self._pv
        # 3D iso view
        self._plotter.subplot(0, 0)
        self._plotter.add_axes(interactive=False)
        self._plotter.add_text("3D", position="upper_left", font_size=10)
        self._plotter.show_grid()
        self._tool_actor_3d = self._plotter.add_mesh(
            pv.Sphere(radius=0.5, center=(0.0, 0.0, 0.0)),
            color="red",
            name="tool_3d",
        )

        # Top-down view
        self._plotter.subplot(0, 1)
        self._plotter.add_text("Top (XY)", position="upper_left", font_size=10)
        self._plotter.show_grid()
        self._plotter.view_xy()
        self._tool_actor_top = self._plotter.add_mesh(
            pv.Sphere(radius=0.5, center=(0.0, 0.0, 0.0)),
            color="red",
            name="tool_top",
        )

    # ------------------------------------------------------------------
    # Backend protocol
    # ------------------------------------------------------------------

    def is_authoritative(self) -> bool:
        return False

    def send(self, line: str, *, blocking: bool = True) -> BackendResult:
        del blocking
        event = self._parser.consume(line)
        if event is not None:
            self._events.put(event)
        return BackendResult(ok=True)

    def status(self) -> MachineStatus:
        pos = self._parser.position
        return MachineStatus(
            state="Visualizer",
            mpos=pos,
            wpos=pos,
            buffer_free=0,
        )

    def stop(self, *, soft: bool = True) -> None:
        del soft
        self._events.put(AlarmEvent("stop"))

    def close(self) -> None:
        try:
            self._plotter.close()
        except Exception as exc:  # noqa: BLE001
            log.warning("Plotter close raised: %s", exc)

    def update_stock(self, stock: Stock) -> None:
        self._events.put(StockEvent(size=stock.size, anchor=stock.anchor))

    # ------------------------------------------------------------------
    # Event handling (G-code → events; events → VTK actors)
    # ------------------------------------------------------------------

    def _drain_queue(self) -> None:
        """Runs on the Qt GUI thread (pyvistaqt timer callback)."""
        try:
            while True:
                event = self._events.get_nowait()
                self._apply_event(event)
        except queue.Empty:
            pass

    def _apply_event(self, event: VizEvent) -> None:
        if isinstance(event, ToolMoveEvent):
            self._draw_segment(event)
            return
        if isinstance(event, StockEvent):
            self._draw_stock(event)
            return
        if isinstance(event, ClearEvent):
            self._clear()
            return
        if isinstance(event, AlarmEvent):
            self._flash_alarm()
            return

    def _draw_segment(self, ev: ToolMoveEvent) -> None:
        pv = self._pv
        # The "previous" point is currently displayed by the tool sphere.
        # We don't track it across events to keep state simple — the segment
        # between the prior tip and the new target is what we draw.
        prev = self._last_drawn_position()
        if prev is None or prev == ev.target:
            self._move_tool_to(ev.target)
            self._prev_position = ev.target
            return
        line = pv.Line(
            (prev.x, prev.y, prev.z),
            (ev.target.x, ev.target.y, ev.target.z),
        )
        color = "gray" if ev.kind == "G0" else "blue"
        for sub in (0, 1):
            self._plotter.subplot(0, sub)
            self._plotter.add_mesh(line, color=color, line_width=2 if ev.kind == "G1" else 1)
        self._move_tool_to(ev.target)
        self._prev_position = ev.target

    def _last_drawn_position(self) -> Vec3 | None:
        return getattr(self, "_prev_position", None)

    def _move_tool_to(self, pos: Vec3) -> None:
        pv = self._pv
        sphere = pv.Sphere(radius=0.5, center=(pos.x, pos.y, pos.z))
        for sub, name in [(0, "tool_3d"), (1, "tool_top")]:
            self._plotter.subplot(0, sub)
            self._plotter.remove_actor(name, render=False)
            self._plotter.add_mesh(sphere, color="red", name=name)

    def _draw_stock(self, ev: StockEvent) -> None:
        pv = self._pv
        cx = ev.anchor.x + ev.size.x / 2.0
        cy = ev.anchor.y + ev.size.y / 2.0
        cz = ev.anchor.z - ev.size.z / 2.0
        bounds = (
            cx - ev.size.x / 2.0, cx + ev.size.x / 2.0,
            cy - ev.size.y / 2.0, cy + ev.size.y / 2.0,
            cz - ev.size.z / 2.0, cz + ev.size.z / 2.0,
        )
        box = pv.Box(bounds=bounds)
        for sub, name in [(0, "stock_3d"), (1, "stock_top")]:
            self._plotter.subplot(0, sub)
            self._plotter.remove_actor(name, render=False)
            self._plotter.add_mesh(box, color="tan", opacity=0.2, name=name)

    def _clear(self) -> None:
        for sub in (0, 1):
            self._plotter.subplot(0, sub)
            self._plotter.clear()
        self._setup_views()

    def _flash_alarm(self) -> None:
        for sub in (0, 1):
            self._plotter.subplot(0, sub)
            self._plotter.set_background("red")

    @property
    def queued_events(self) -> int:
        return self._events.qsize()
