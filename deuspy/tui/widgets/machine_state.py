"""Live machine state panel — shown in the REPL screen."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container
from textual.reactive import reactive
from textual.widgets import Static


class MachineStatePanel(Container):
    """Updates every ~250 ms from the deuspy Machine singleton."""

    DEFAULT_CSS = """
    MachineStatePanel {
        border: round #00d4ff;
        background: #181826;
        padding: 0 1;
        layout: vertical;
        width: 28;
        height: auto;
    }
    MachineStatePanel > .title {
        content-align: center middle;
        color: #00d4ff;
        text-style: bold;
        height: 1;
    }
    .state-row {
        height: 1;
    }
    .state-led { height: 1; content-align: center middle; }
    """

    state_text: reactive[Text] = reactive(Text(), recompose=False)

    def compose(self) -> ComposeResult:
        yield Static("◆ MACHINE ◆", classes="title")
        yield Static(id="state-body")
        yield Static("[#4a4a6a]●[/] disconnected", id="state-led", classes="state-led")

    def on_mount(self) -> None:
        self.set_interval(0.25, self._refresh)
        self._refresh()

    def _refresh(self) -> None:
        from deuspy.machine import get_machine

        m = get_machine()
        connected = bool(m.backends)
        led = (
            "[#00ff88 bold]● CONNECTED[/]"
            if connected
            else "[#4a4a6a]● disconnected[/]"
        )
        if m.state.name == "HALTED":
            led = "[#ff3366 bold]● HALTED[/]"
        self.query_one("#state-led", Static).update(led)

        spindle = (
            f"[#00ff88]{m.spindle_rpm:.0f} rpm[/]"
            if m.spindle_rpm > 0
            else "[#8080a0]OFF[/]"
        )
        wcs_label = f"G5{3 + m.wcs_slot}" if 1 <= m.wcs_slot <= 6 else "?"
        body = (
            f"[#8080a0]Position[/]\n"
            f"  [#8080a0]X[/] [#00d4ff bold]{m.position.x:9.3f}[/]\n"
            f"  [#8080a0]Y[/] [#00d4ff bold]{m.position.y:9.3f}[/]\n"
            f"  [#8080a0]Z[/] [#00d4ff bold]{m.position.z:9.3f}[/]\n"
            f"\n"
            f"[#8080a0]Units[/]    [#a855f7]{m.units.value.upper()}[/]\n"
            f"[#8080a0]Feed[/]     [#a855f7]{m.feed:g}[/]\n"
            f"[#8080a0]Spindle[/]  {spindle}\n"
            f"[#8080a0]WCS[/]      [#fbbf24]{wcs_label}[/]\n"
            f"[#8080a0]Tool Ø[/]   [#a855f7]{m.tool.diameter:g}[/]\n"
            f"[#8080a0]Safe Z[/]   [#a855f7]{m.safe_z:g}[/]\n"
        )
        if m.stock is not None:
            body += (
                f"\n[#8080a0]Stock[/]\n"
                f"  [#00d4ff]{m.stock.size.x:g}×{m.stock.size.y:g}×{m.stock.size.z:g}[/]\n"
            )
        self.query_one("#state-body", Static).update(body)
