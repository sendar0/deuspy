"""Jog pad — directional buttons in a 3×3 grid + step size selector."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Grid, Horizontal
from textual.message import Message
from textual.widgets import Button, Input, Static


class JogPad(Container):
    """Emits Jog messages when the user presses directional buttons."""

    DEFAULT_CSS = """
    JogPad {
        layout: vertical;
        border: round $surface;
        background: $surface;
        padding: 0 1;
    }
    JogPad:focus-within { border: round cyan; }
    JogPad > .title {
        content-align: center middle;
        color: cyan;
        text-style: bold;
        height: 1;
        background: $boost;
    }
    JogPad > Grid {
        grid-size: 3 3;
        grid-gutter: 0 1;
        height: 9;
        margin-top: 1;
    }
    JogPad Button {
        width: 100%;
        height: 100%;
        min-width: 0;
    }
    .jog-spacer { width: 100%; height: 100%; }
    JogPad > .z-row {
        layout: horizontal;
        height: 3;
        margin-top: 1;
        align: center middle;
    }
    JogPad > .step-row {
        layout: horizontal;
        height: 3;
        margin-top: 1;
        align: center middle;
    }
    .step-label {
        width: 6;
        color: $text-muted;
        padding: 1 1;
    }
    """

    class Jog(Message):
        def __init__(self, dx: float, dy: float, dz: float) -> None:
            self.dx, self.dy, self.dz = dx, dy, dz
            super().__init__()

    def compose(self) -> ComposeResult:
        yield Static("◆ JOG ◆", classes="title")
        with Grid():
            yield Static(classes="jog-spacer")
            yield Button("↑ Y+", id="jog-yp", variant="primary")
            yield Static(classes="jog-spacer")
            yield Button("X- ←", id="jog-xn", variant="primary")
            yield Static(classes="jog-spacer")
            yield Button("→ X+", id="jog-xp", variant="primary")
            yield Static(classes="jog-spacer")
            yield Button("↓ Y-", id="jog-yn", variant="primary")
            yield Static(classes="jog-spacer")
        with Horizontal(classes="z-row"):
            yield Button("Z+", id="jog-zp", variant="warning")
            yield Button("Z-", id="jog-zn", variant="warning")
        with Horizontal(classes="step-row"):
            yield Static("step", classes="step-label")
            yield Input(value="1.0", id="jog-step-input")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        try:
            step = float(self.query_one("#jog-step-input", Input).value or "1")
        except ValueError:
            step = 1.0
        delta = {
            "jog-xp": (step, 0, 0),
            "jog-xn": (-step, 0, 0),
            "jog-yp": (0, step, 0),
            "jog-yn": (0, -step, 0),
            "jog-zp": (0, 0, step),
            "jog-zn": (0, 0, -step),
        }.get(bid)
        if delta is None:
            return
        self.post_message(self.Jog(*delta))
