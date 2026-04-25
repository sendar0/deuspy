"""REPL tab: live state + history + command input + quick actions."""

from __future__ import annotations

import contextlib
import io
import traceback
from typing import Any

from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, RichLog, Static

from deuspy.tui.widgets.jog_pad import JogPad
from deuspy.tui.widgets.machine_state import MachineStatePanel


class StockDialog(ModalScreen[tuple[float, float, float] | None]):
    """Modal for setting stock dimensions."""

    CSS = """
    StockDialog { align: center middle; }
    #stock-card {
        width: 50; height: auto;
        background: #181826;
        border: round #00d4ff;
        padding: 1 2;
    }
    #stock-title {
        content-align: center middle;
        color: #00d4ff;
        text-style: bold;
        margin-bottom: 1;
    }
    .stock-row { height: 3; }
    .stock-label { width: 8; color: #8080a0; padding: 1 1; }
    .stock-input { width: 1fr; }
    #stock-buttons { margin-top: 1; align: center middle; }
    """

    BINDINGS = [("escape", "dismiss(None)", "Cancel")]

    def __init__(self, current: tuple[float, float, float] = (100.0, 100.0, 20.0)) -> None:
        super().__init__()
        self._current = current

    def compose(self) -> ComposeResult:
        with Vertical(id="stock-card"):
            yield Static("◆ SET STOCK ◆", id="stock-title")
            with Horizontal(classes="stock-row"):
                yield Label("X (mm)", classes="stock-label")
                yield Input(value=str(self._current[0]), id="stock-x", classes="stock-input")
            with Horizontal(classes="stock-row"):
                yield Label("Y (mm)", classes="stock-label")
                yield Input(value=str(self._current[1]), id="stock-y", classes="stock-input")
            with Horizontal(classes="stock-row"):
                yield Label("Z (mm)", classes="stock-label")
                yield Input(value=str(self._current[2]), id="stock-z", classes="stock-input")
            with Horizontal(id="stock-buttons"):
                yield Button("Save", variant="primary", id="stock-save")
                yield Button("Cancel", id="stock-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "stock-cancel":
            self.dismiss(None)
            return
        try:
            x = float(self.query_one("#stock-x", Input).value)
            y = float(self.query_one("#stock-y", Input).value)
            z = float(self.query_one("#stock-z", Input).value)
        except ValueError:
            self.app.notify("Numbers please.", severity="error")
            return
        self.dismiss((x, y, z))


class ToolDialog(ModalScreen[tuple[float, str] | None]):
    """Modal for changing the active tool diameter."""

    CSS = """
    ToolDialog { align: center middle; }
    #tool-card {
        width: 50; height: auto;
        background: #181826;
        border: round #ff00aa;
        padding: 1 2;
    }
    #tool-title {
        content-align: center middle;
        color: #ff00aa;
        text-style: bold;
        margin-bottom: 1;
    }
    .tool-row { height: 3; }
    .tool-label { width: 14; color: #8080a0; padding: 1 1; }
    .tool-input { width: 1fr; }
    #tool-buttons { margin-top: 1; align: center middle; }
    """

    BINDINGS = [("escape", "dismiss(None)", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(id="tool-card"):
            yield Static("◆ TOOL CHANGE ◆", id="tool-title")
            with Horizontal(classes="tool-row"):
                yield Label("Diameter", classes="tool-label")
                yield Input(value="3.0", id="tool-d", classes="tool-input")
            with Horizontal(classes="tool-row"):
                yield Label("Name", classes="tool-label")
                yield Input(placeholder="optional", id="tool-name", classes="tool-input")
            with Horizontal(id="tool-buttons"):
                yield Button("Save", variant="primary", id="tool-save")
                yield Button("Cancel", id="tool-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "tool-cancel":
            self.dismiss(None)
            return
        try:
            d = float(self.query_one("#tool-d", Input).value)
        except ValueError:
            self.app.notify("Diameter must be a number.", severity="error")
            return
        name = self.query_one("#tool-name", Input).value
        self.dismiss((d, name))


class ReplScreen(Container):
    """Three-column REPL: state | history+input | actions+jog."""

    DEFAULT_CSS = """
    ReplScreen {
        layout: horizontal;
        padding: 1 2;
    }
    #repl-left {
        width: 30;
        height: 1fr;
    }
    #repl-center {
        width: 1fr;
        height: 1fr;
        margin: 0 1;
    }
    #repl-right {
        width: 30;
        height: 1fr;
    }
    #history-panel {
        height: 1fr;
        border: round #a855f7;
        background: #0a0a14;
    }
    #history-title {
        content-align: center middle;
        color: #a855f7;
        text-style: bold;
        height: 1;
        background: #181826;
    }
    #history-log {
        height: 1fr;
        background: #0a0a14;
    }
    #cmd-row {
        height: 3;
        margin-top: 1;
    }
    #cmd-prompt {
        width: 5;
        color: #00ff88;
        padding: 1 1;
        text-style: bold;
    }
    #cmd-input { width: 1fr; }
    .actions-card {
        border: round #00ff88;
        background: #181826;
        padding: 0 1;
        height: auto;
        margin-bottom: 1;
    }
    .actions-card > .title {
        content-align: center middle;
        color: #00ff88;
        text-style: bold;
        height: 1;
    }
    .action-btn {
        width: 100%;
        margin: 0 0;
    }
    """

    PRELUDE = """\
[bold #ff00aa]deuspy REPL[/]   [#8080a0]· deuspy module pre-imported as `d` ·[/]
[#8080a0]Examples:[/]
  [#00d4ff]d.move(d.origin)[/]                  · [#00d4ff]d.set_units(d.MM)[/]
  [#00d4ff]d.set_movement_speed(100)[/]         · [#00d4ff]d.move(x=2, y=2)[/]
  [#00d4ff]d.execute(d.Box(length=4, width=4, height=2))[/]
[#8080a0]Type any Python expression. Use the buttons on the right for common actions.[/]
"""

    def __init__(self) -> None:
        super().__init__()
        self._history: list[str] = []
        self._history_idx: int = 0
        # Persistent eval namespace.
        import deuspy
        self._namespace: dict[str, Any] = {"d": deuspy, "deuspy": deuspy, "__name__": "__deuspy_repl__"}

    def compose(self) -> ComposeResult:
        with Vertical(id="repl-left"):
            yield MachineStatePanel()
        with Vertical(id="repl-center"):
            with Vertical(id="history-panel"):
                yield Static("◆ HISTORY ◆", id="history-title")
                yield RichLog(id="history-log", highlight=True, markup=True, wrap=True)
            with Horizontal(id="cmd-row"):
                yield Static(">>>", id="cmd-prompt")
                yield Input(placeholder="Python expression — e.g. d.move(x=2, y=2)", id="cmd-input")
        with Vertical(id="repl-right"):
            with Vertical(classes="actions-card"):
                yield Static("◆ MOTION ◆", classes="title")
                yield Button("⌂ HOME", id="act-home", classes="action-btn")
                yield Button("◯ ORIGIN", id="act-origin", classes="action-btn")
                yield Button("✛ CENTER", id="act-center", classes="action-btn")
                yield Button("⏏ SAFE Z", id="act-safe", classes="action-btn")
                yield Button("✖ STOP!", id="act-stop", classes="action-btn", variant="error")
            with Vertical(classes="actions-card"):
                yield Static("◆ SETUP ◆", classes="title")
                yield Button("📦 STOCK", id="act-stock", classes="action-btn")
                yield Button("⚙ TOOL", id="act-tool", classes="action-btn")
                yield Button("🎯 SET ORIGIN", id="act-set-origin", classes="action-btn")
                yield Button("🔓 UNLOCK", id="act-unlock", classes="action-btn", variant="warning")
            yield JogPad()

    def on_mount(self) -> None:
        log = self.query_one("#history-log", RichLog)
        log.write(self.PRELUDE)
        self.query_one("#cmd-input", Input).focus()

    # ---- command input ------------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "cmd-input":
            return
        cmd = event.value
        event.input.value = ""
        if not cmd.strip():
            return
        self._history.append(cmd)
        self._history_idx = len(self._history)
        self._eval(cmd)

    def on_key(self, event) -> None:
        if not isinstance(self.app.focused, Input):
            return
        focused = self.app.focused
        if focused.id != "cmd-input":
            return
        if event.key == "up":
            if self._history and self._history_idx > 0:
                self._history_idx -= 1
                focused.value = self._history[self._history_idx]
                event.stop()
        elif event.key == "down":
            if self._history and self._history_idx < len(self._history) - 1:
                self._history_idx += 1
                focused.value = self._history[self._history_idx]
                event.stop()
            elif self._history_idx == len(self._history) - 1:
                self._history_idx = len(self._history)
                focused.value = ""
                event.stop()

    def _eval(self, cmd: str) -> None:
        log = self.query_one("#history-log", RichLog)
        log.write(f"[#00ff88]>>> [/]{cmd}")
        out_buf = io.StringIO()
        err_buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(err_buf):
                # First try as expression so we can echo the result.
                try:
                    code = compile(cmd, "<repl>", "eval")
                    result = eval(code, self._namespace)  # noqa: S307 — explicit user input
                    if result is not None:
                        print(repr(result))
                except SyntaxError:
                    code = compile(cmd, "<repl>", "exec")
                    exec(code, self._namespace)  # noqa: S102
        except Exception:  # noqa: BLE001
            err_buf.write(traceback.format_exc())

        out = out_buf.getvalue()
        err = err_buf.getvalue()
        if out:
            log.write(out.rstrip())
        if err:
            log.write(f"[#ff3366]{err.rstrip()}[/]")

    # ---- quick actions ------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "act-home":
            self._safe_call("d.home()")
        elif bid == "act-origin":
            self._safe_call("d.move(d.origin)")
        elif bid == "act-center":
            self._move_to_stock_center()
        elif bid == "act-safe":
            self._safe_call("d.move(z=d.status().wpos.z if False else d.get_machine().safe_z, rapid=True)")
        elif bid == "act-stop":
            self._safe_call("d.stop()")
        elif bid == "act-stock":
            self._set_stock_dialog()
        elif bid == "act-tool":
            self._tool_dialog()
        elif bid == "act-set-origin":
            self._safe_call("d.set_origin(d.origin)")
        elif bid == "act-unlock":
            self._safe_call("d.unlock()")

    def _safe_call(self, cmd: str) -> None:
        # Make d.get_machine accessible.
        from deuspy.machine import get_machine
        self._namespace.setdefault("get_machine", get_machine)
        self._eval(cmd)

    def _move_to_stock_center(self) -> None:
        from deuspy.machine import get_machine
        m = get_machine()
        if not m.backends:
            self._not_connected()
            return
        if m.stock is None:
            self.app.notify("No stock defined. Set stock first.", severity="warning")
            return
        cx = m.stock.anchor.x + m.stock.size.x / 2
        cy = m.stock.anchor.y + m.stock.size.y / 2
        self._eval(f"d.move(x={cx:g}, y={cy:g})")

    def _not_connected(self) -> None:
        self.app.notify("Not connected. Use the Machines tab to connect.", severity="warning")

    @work
    async def _set_stock_dialog(self) -> None:
        from deuspy.machine import get_machine
        m = get_machine()
        current = (m.stock.size.x, m.stock.size.y, m.stock.size.z) if m.stock else (100.0, 100.0, 20.0)
        result = await self.app.push_screen_wait(StockDialog(current))
        if result is None:
            return
        x, y, z = result
        self._eval(f"d.set_stock(d.Vec3({x}, {y}, {z}))")

    @work
    async def _tool_dialog(self) -> None:
        result = await self.app.push_screen_wait(ToolDialog())
        if result is None:
            return
        d, name = result
        self._eval(f"d.set_tool(d.Tool(diameter={d}, name={name!r}))")

    # ---- jog pad ------------------------------------------------------------

    def on_jog_pad_jog(self, message: JogPad.Jog) -> None:
        from deuspy.machine import get_machine
        m = get_machine()
        if not m.backends:
            self._not_connected()
            return
        parts = []
        if message.dx:
            parts.append(f"x={message.dx:g}")
        if message.dy:
            parts.append(f"y={message.dy:g}")
        if message.dz:
            parts.append(f"z={message.dz:g}")
        if not parts:
            return
        self._eval(f"d.move({', '.join(parts)}, relative=True, rapid=True)")
