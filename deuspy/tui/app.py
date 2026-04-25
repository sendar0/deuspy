"""deuspy TUI — Textual application shell."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane

from deuspy.tui.screens.designer import DesignerScreen
from deuspy.tui.screens.machines import MachinesScreen
from deuspy.tui.screens.repl import ReplScreen
from deuspy.tui.splash import SplashScreen
from deuspy.tui.state import ProfileStore

CSS_PATH = Path(__file__).with_name("theme.tcss")


class DeuspyApp(App[None]):
    """The top-level Textual app for deuspy.

    Layout:
      - Splash screen on startup (animated; auto-dismisses).
      - Main shell with three tabs: Machines, Designer, REPL.
    """

    CSS_PATH = str(CSS_PATH)
    TITLE = "deuspy"
    SUB_TITLE = "deus py machina · interactive GRBL CNC"
    # Tokyo-night ships with Textual and matches the cyberpunk-neon vibe.
    # Users can swap this at runtime via :command and the theme switcher.
    THEME = "tokyo-night"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("1", "tab('machines')", "Machines"),
        Binding("2", "tab('designer')", "Designer"),
        Binding("3", "tab('repl')", "REPL"),
        Binding("ctrl+t", "toggle_theme", "Theme", show=False),
        Binding("?", "help", "Help"),
    ]

    _THEMES = ["tokyo-night", "dracula", "monokai", "nord", "gruvbox", "catppuccin-mocha", "textual-dark"]

    def __init__(self) -> None:
        super().__init__()
        self.store: ProfileStore = ProfileStore.load()
        self._theme_idx = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="machines", id="main-tabs"):
            with TabPane("◆ MACHINES", id="machines"):
                yield MachinesScreen()
            with TabPane("◆ DESIGNER", id="designer"):
                yield DesignerScreen()
            with TabPane("◆ REPL", id="repl"):
                yield ReplScreen()
        yield Static(self._status_text(), id="status-bar")
        yield Footer()

    def _status_text(self) -> str:
        from deuspy.machine import get_machine
        m = get_machine()
        active = self.store.active or "—"
        if m.backends:
            led = "[green bold]● connected[/]"
        elif m.state.name == "HALTED":
            led = "[red bold]● halted[/]"
        else:
            led = "[dim]○ disconnected[/]"
        return (
            f"  [b cyan]deuspy[/] · profile [b]{active}[/] · {led}"
            f" · units [b]{m.units.value.upper()}[/]"
            f" · feed [b]{m.feed:g}[/]"
            f" · WCS [b]G5{3 + m.wcs_slot}[/]"
            f" · [dim]theme {self.THEME}[/]"
        )

    def on_mount(self) -> None:
        try:
            self.theme = self.THEME
        except Exception:  # noqa: BLE001 — fall back to default if theme unavailable
            pass
        # Force the initial tab after layout settles — Textual otherwise
        # auto-activates the last child despite TabbedContent(initial=...).
        self.call_after_refresh(self._set_initial_tab)
        # Refresh the status strip every half second.
        self.set_interval(0.5, self._refresh_status)
        # Splash plays first; the user lands on the main shell after.
        self.push_screen(SplashScreen())

    def _refresh_status(self) -> None:
        try:
            self.query_one("#status-bar", Static).update(self._status_text())
        except Exception:  # noqa: BLE001
            pass

    def _set_initial_tab(self) -> None:
        self.query_one(TabbedContent).active = "machines"

    def action_tab(self, tab_id: str) -> None:
        self.query_one(TabbedContent).active = tab_id

    def action_toggle_theme(self) -> None:
        self._theme_idx = (self._theme_idx + 1) % len(self._THEMES)
        self.THEME = self._THEMES[self._theme_idx]
        try:
            self.theme = self.THEME
            self.notify(f"Theme: {self.THEME}", severity="information", timeout=2)
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Theme {self.THEME!r} unavailable: {exc}", severity="warning")

    def action_help(self) -> None:
        self.notify(
            "1/2/3 switch tabs · q quits · ctrl-T cycles theme · enter runs REPL command",
            title="deuspy",
            severity="information",
        )

    def save_store(self) -> None:
        try:
            self.store.save()
        except OSError as exc:
            self.notify(f"Could not save machines: {exc}", severity="error")


def run() -> None:
    """Entry point used by the `deuspy-tui` console script."""
    DeuspyApp().run()


if __name__ == "__main__":
    run()
