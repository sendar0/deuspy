"""TUI smoke tests using Textual's Pilot harness."""

from __future__ import annotations

import pytest

textual = pytest.importorskip("textual")

from deuspy.shapes import Polyline  # noqa: E402
from deuspy.tui.app import DeuspyApp  # noqa: E402
from deuspy.tui.state import MachineProfile, ProfileStore  # noqa: E402

# --- Star factory ------------------------------------------------------------


def test_star_factory_produces_2n_points():
    s = Polyline.star(points=5, outer_radius=10, inner_radius=4, depth=1)
    assert len(s.points) == 10
    assert s.closed is True


def test_star_validates_inputs():
    with pytest.raises(ValueError):
        Polyline.star(points=2, outer_radius=10, inner_radius=4, depth=1)
    with pytest.raises(ValueError):
        Polyline.star(points=5, outer_radius=4, inner_radius=4, depth=1)
    with pytest.raises(ValueError):
        Polyline.star(points=5, outer_radius=4, inner_radius=10, depth=1)


# --- Profile store -----------------------------------------------------------


def test_profile_store_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    store = ProfileStore.load()
    assert store.profiles == []
    store.upsert(MachineProfile(name="bench", port="/dev/ttyUSB0"))
    store.upsert(MachineProfile(name="garage", port=""))
    store.active = "bench"
    store.save()

    again = ProfileStore.load()
    names = sorted(p.name for p in again.profiles)
    assert names == ["bench", "garage"]
    assert again.active == "bench"
    assert again.get("bench").port == "/dev/ttyUSB0"


def test_profile_store_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    store = ProfileStore.load()
    store.upsert(MachineProfile(name="x"))
    store.upsert(MachineProfile(name="y"))
    store.active = "x"
    assert store.delete("x") is True
    assert store.active is None
    assert store.delete("nope") is False


# --- TUI: Pilot smoke tests --------------------------------------------------


@pytest.mark.asyncio
async def test_app_boots_and_dismisses_splash(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    app = DeuspyApp()
    async with app.run_test() as pilot:
        # Splash is the active screen on boot.
        from deuspy.tui.splash import SplashScreen
        assert isinstance(app.screen, SplashScreen)
        # Skip the splash with Enter.
        await pilot.press("enter")
        await pilot.pause()
        # Now the default screen with the tabs should be active.
        from textual.widgets import TabbedContent
        tabs = app.query_one(TabbedContent)
        assert tabs.active == "machines"


@pytest.mark.asyncio
async def test_app_tab_switching(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    app = DeuspyApp()
    async with app.run_test() as pilot:
        await pilot.press("enter")  # dismiss splash
        await pilot.pause()
        from textual.widgets import TabbedContent
        tabs = app.query_one(TabbedContent)
        await pilot.press("2")
        await pilot.pause()
        assert tabs.active == "designer"
        await pilot.press("3")
        await pilot.pause()
        assert tabs.active == "repl"
        await pilot.press("1")
        await pilot.pause()
        assert tabs.active == "machines"


@pytest.mark.asyncio
async def test_designer_dry_run_generates_toolpath(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    app = DeuspyApp()
    async with app.run_test(size=(160, 50)) as pilot:
        await pilot.press("enter")  # dismiss splash
        await pilot.press("2")      # designer tab
        await pilot.pause()
        from deuspy.tui.screens.designer import DesignerScreen
        screen = app.query_one(DesignerScreen)
        # Trigger the dry-run path directly (avoids click coordinate issues
        # with terminals smaller than the layout demands).
        screen._run_preview()
        await pilot.pause()
        assert getattr(screen, "_last_tp", None) is not None
        assert len(screen._last_tp) > 0


@pytest.mark.asyncio
async def test_repl_evaluates_command_and_logs(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    app = DeuspyApp()
    async with app.run_test() as pilot:
        await pilot.press("enter")  # dismiss splash
        await pilot.press("3")      # REPL tab
        await pilot.pause()
        from textual.widgets import Input

        from deuspy.tui.screens.repl import ReplScreen
        repl = app.query_one(ReplScreen)
        cmd = app.query_one("#cmd-input", Input)
        cmd.focus()
        # Run a command with a side effect we can verify in the namespace.
        cmd.value = "_test_x = 21 * 2"
        await pilot.press("enter")
        await pilot.pause()
        assert repl._namespace.get("_test_x") == 42
