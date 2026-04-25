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
    SUB_TITLE = "deus py machina"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("1", "tab('machines')", "Machines"),
        Binding("2", "tab('designer')", "Designer"),
        Binding("3", "tab('repl')", "REPL"),
        Binding("?", "help", "Help"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.store: ProfileStore = ProfileStore.load()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(
            "▓ deuspy · interactive GRBL CNC control · press ? for help ▓",
            id="main-title",
        )
        with TabbedContent(initial="machines", id="main-tabs"):
            with TabPane("◆ MACHINES", id="machines"):
                yield MachinesScreen()
            with TabPane("◆ DESIGNER", id="designer"):
                yield DesignerScreen()
            with TabPane("◆ REPL", id="repl"):
                yield ReplScreen()
        yield Footer()

    def on_mount(self) -> None:
        # Force the initial tab after layout settles — Textual otherwise
        # auto-activates the last child despite TabbedContent(initial=...).
        self.call_after_refresh(self._set_initial_tab)
        # Splash plays first; the user lands on the main shell after.
        self.push_screen(SplashScreen())

    def _set_initial_tab(self) -> None:
        self.query_one(TabbedContent).active = "machines"

    def action_tab(self, tab_id: str) -> None:
        self.query_one(TabbedContent).active = tab_id

    def action_help(self) -> None:
        self.notify(
            "1/2/3 switch tabs · q quits · enter runs commands in REPL",
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
