"""Animated splash screen for the deuspy TUI."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Center, Middle, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import ProgressBar, Static

# Clean figlet-style logo (block characters), wider than tall.
LOGO = r"""
 ▄▄▄▄    ▄▄▄▄▄▄  ▄▄  ▄▄   ▄▄▄▄   ▄▄▄▄▄    ▄▄  ▄▄
 ██▀▀█▄  ██▀▀▀▀  ██  ██  ██▀▀▀▀  ██▀▀██▀  ██  ██
 ██   ██ █████   ██  ██  ▀▀████  ██████   ██▄▄██
 ██   ██ ██      ██  ██  ▄▄  ██  ██       ▀▀▀▀██
 ██▄▄█▀  ██▄▄▄▄▄ ▀█▄▄█▀  ▀█▄▄█▀  ██       ▄▄▄▄██
"""

TAGLINE = "deus py machina · interactive GRBL CNC control"
HINTS = [
    "warming the spindle",
    "homing axes",
    "checking limit switches",
    "calibrating dreams",
    "polishing the bits",
    "dust collector: ready",
    "summoning subroutines",
    "waxing the ways",
    "tightening the collet",
]


class SplashLogo(Static):
    """The big logo with a pulsing colour glow that cycles through theme accents."""

    DEFAULT_CSS = """
    SplashLogo {
        content-align: center middle;
        width: auto;
        height: auto;
        text-style: bold;
    }
    """

    pulse: reactive[int] = reactive(0)

    def render(self) -> str:
        # Cycle through theme tokens so it tracks the active palette.
        tokens = ["magenta", "cyan", "green", "yellow", "cyan"]
        token = tokens[self.pulse % len(tokens)]
        return f"[{token}]{LOGO}[/]"


class SplashScreen(Screen):
    """Animated startup screen.

    Plays for ~2.4 s, then dismisses itself. The user can also press any key
    or click to skip ahead.
    """

    DEFAULT_CSS = """
    SplashScreen {
        background: $background;
        align: center middle;
    }
    #splash-stack {
        width: auto;
        height: auto;
        align: center middle;
    }
    #splash-tagline {
        content-align: center middle;
        color: $text-muted;
        text-style: italic;
        margin-top: 1;
    }
    #splash-hint {
        content-align: center middle;
        color: cyan;
        margin-top: 1;
        width: 60;
    }
    #splash-bar {
        margin-top: 2;
        width: 60;
    }
    #splash-skip {
        content-align: center middle;
        color: $text-muted;
        margin-top: 2;
    }
    """

    BINDINGS = [
        ("escape", "skip", "Skip"),
        ("enter", "skip", "Skip"),
        ("space", "skip", "Skip"),
    ]

    def compose(self) -> ComposeResult:
        with Middle(), Center(), Vertical(id="splash-stack"):
            yield SplashLogo(id="splash-logo")
            yield Static(TAGLINE, id="splash-tagline")
            yield Static("[ booting ]", id="splash-hint")
            yield ProgressBar(total=100, show_eta=False, show_percentage=False, id="splash-bar")
            yield Static("press [b]enter[/] to skip", id="splash-skip")

    def on_mount(self) -> None:
        # Pulse the logo every 120 ms.
        self._pulse_timer = self.set_interval(0.12, self._tick_pulse)
        # Cycle hint text every 360 ms.
        self._hint_timer = self.set_interval(0.36, self._tick_hint)
        self._hint_index = 0
        # Drive the progress bar manually.
        self._fill_progress()

    def _tick_pulse(self) -> None:
        logo = self.query_one(SplashLogo)
        logo.pulse += 1

    def _tick_hint(self) -> None:
        self._hint_index = (self._hint_index + 1) % len(HINTS)
        self.query_one("#splash-hint", Static).update(f"[ {HINTS[self._hint_index]} ]")

    @work
    async def _fill_progress(self) -> None:
        bar = self.query_one(ProgressBar)
        for i in range(0, 101, 5):
            bar.update(progress=i)
            await self._sleep(0.10)
        # Done — hand off to the main app.
        self.action_skip()

    async def _sleep(self, seconds: float) -> None:
        import asyncio
        await asyncio.sleep(seconds)

    def action_skip(self) -> None:
        if hasattr(self, "_pulse_timer"):
            self._pulse_timer.stop()
        if hasattr(self, "_hint_timer"):
            self._hint_timer.stop()
        # Pop the splash so the main shell shows.
        if self.is_attached:
            self.app.pop_screen()
