"""Jog pad — directional buttons + step size selector."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.message import Message
from textual.widgets import Button, Input, Static


class JogPad(Container):
    """Emits Jog messages when the user presses directional buttons."""

    DEFAULT_CSS = """
    JogPad {
        border: round #ff00aa;
        background: #181826;
        padding: 0 1;
        layout: vertical;
        width: 28;
        height: auto;
    }
    JogPad > .title {
        content-align: center middle;
        color: #ff00aa;
        text-style: bold;
        height: 1;
    }
    .jog-row {
        height: 3;
        align: center middle;
    }
    .jog-btn {
        width: 8;
        min-width: 6;
        margin: 0 0;
    }
    .jog-step {
        height: 3;
        align: center middle;
    }
    """

    class Jog(Message):
        def __init__(self, dx: float, dy: float, dz: float) -> None:
            self.dx, self.dy, self.dz = dx, dy, dz
            super().__init__()

    def compose(self) -> ComposeResult:
        yield Static("◆ JOG ◆", classes="title")
        with Horizontal(classes="jog-row"):
            yield Button(" ", classes="jog-btn", disabled=True)
            yield Button("↑ Y+", classes="jog-btn", id="jog-yp")
            yield Button(" ", classes="jog-btn", disabled=True)
        with Horizontal(classes="jog-row"):
            yield Button("← X-", classes="jog-btn", id="jog-xn")
            yield Button("⌂ ", classes="jog-btn", id="jog-zero", disabled=True)
            yield Button("X+ →", classes="jog-btn", id="jog-xp")
        with Horizontal(classes="jog-row"):
            yield Button(" ", classes="jog-btn", disabled=True)
            yield Button("↓ Y-", classes="jog-btn", id="jog-yn")
            yield Button(" ", classes="jog-btn", disabled=True)
        with Horizontal(classes="jog-row"):
            yield Button("Z+", classes="jog-btn", id="jog-zp", variant="warning")
            yield Button(" ", classes="jog-btn", disabled=True)
            yield Button("Z-", classes="jog-btn", id="jog-zn", variant="warning")
        with Horizontal(classes="jog-step"):
            yield Static("[#8080a0]Step[/]")
            yield Input(value="1.0", id="jog-step-input", classes="form-input")

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
