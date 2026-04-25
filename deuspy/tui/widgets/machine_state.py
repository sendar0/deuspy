"""Live machine state panel with Digits readouts for X/Y/Z."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Digits, Static


class MachineStatePanel(Container):
    """Updates every ~250 ms from the deuspy Machine singleton."""

    DEFAULT_CSS = """
    MachineStatePanel {
        layout: grid;
        grid-size: 1 5;
        grid-rows: 1 5 1fr 1 1;
        border: round $surface;
        background: $surface;
        padding: 0 1;
    }
    MachineStatePanel:focus-within { border: round cyan; }
    MachineStatePanel > .title {
        content-align: center middle;
        color: cyan;
        text-style: bold;
        background: $boost;
    }
    .axis-row {
        layout: horizontal;
        height: 5;
        align: center middle;
    }
    .axis-label {
        width: 4;
        content-align: center middle;
        color: $text-muted;
        text-style: bold;
    }
    Digits {
        width: 1fr;
        text-align: right;
        color: cyan;
    }
    #state-meta {
        color: $text;
    }
    .state-led {
        content-align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("◆ MACHINE ◆", classes="title")
        with Horizontal(classes="axis-row"):
            yield Static("X", classes="axis-label")
            yield Digits("0.000", id="dro-x")
        with Horizontal(classes="axis-row"):
            yield Static("Y", classes="axis-label")
            yield Digits("0.000", id="dro-y")
        with Horizontal(classes="axis-row"):
            yield Static("Z", classes="axis-label")
            yield Digits("0.000", id="dro-z")
        yield Static("", id="state-meta")
        yield Static("[dim]○ disconnected[/]", id="state-led", classes="state-led")

    def on_mount(self) -> None:
        self.set_interval(0.25, self._refresh)
        self._refresh()

    def _refresh(self) -> None:
        from deuspy.machine import get_machine

        m = get_machine()
        connected = bool(m.backends)
        if m.state.name == "HALTED":
            led = "[red b]● HALTED[/]"
        elif connected:
            led = "[green b]● CONNECTED[/]"
        else:
            led = "[dim]○ disconnected[/]"

        self.query_one("#dro-x", Digits).update(f"{m.position.x:7.3f}")
        self.query_one("#dro-y", Digits).update(f"{m.position.y:7.3f}")
        self.query_one("#dro-z", Digits).update(f"{m.position.z:7.3f}")
        self.query_one("#state-led", Static).update(led)

        spindle = (
            f"[green b]{m.spindle_rpm:.0f}[/] rpm"
            if m.spindle_rpm > 0
            else "[dim]off[/]"
        )
        wcs = f"G5{3 + m.wcs_slot}" if 1 <= m.wcs_slot <= 6 else "?"
        meta = (
            f"[dim]units[/] [b]{m.units.value.upper()}[/]   "
            f"[dim]feed[/] [b]{m.feed:g}[/]\n"
            f"[dim]spindle[/] {spindle}   "
            f"[dim]WCS[/] [b yellow]{wcs}[/]\n"
            f"[dim]tool Ø[/] [b]{m.tool.diameter:g}[/]   "
            f"[dim]safe Z[/] [b]{m.safe_z:g}[/]"
        )
        if m.stock is not None:
            meta += (
                f"\n[dim]stock[/] [cyan]"
                f"{m.stock.size.x:g}×{m.stock.size.y:g}×{m.stock.size.z:g}[/]"
            )
        self.query_one("#state-meta", Static).update(meta)
