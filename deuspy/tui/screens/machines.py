"""Machines tab: list, add, edit, delete, and connect to machine profiles."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Select, Static

from deuspy.tui.state import MachineProfile

if TYPE_CHECKING:
    from deuspy.tui.app import DeuspyApp


class MachineForm(ModalScreen[MachineProfile | None]):
    """Modal for creating or editing a machine profile."""

    CSS = """
    MachineForm {
        align: center middle;
    }
    #form-card {
        width: 70;
        height: auto;
        background: #181826;
        border: round #a855f7;
        padding: 1 2;
    }
    #form-title {
        content-align: center middle;
        color: #ff00aa;
        text-style: bold;
        margin-bottom: 1;
    }
    .form-row {
        height: 3;
        margin-bottom: 0;
    }
    .form-label {
        width: 18;
        color: #8080a0;
        padding: 1 1;
    }
    .form-input { width: 1fr; }
    #form-buttons {
        margin-top: 1;
        align: center middle;
    }
    """

    BINDINGS = [
        ("escape", "dismiss(None)", "Cancel"),
    ]

    def __init__(self, profile: MachineProfile | None = None) -> None:
        super().__init__()
        self._initial = profile
        self._editing = profile is not None

    def compose(self) -> ComposeResult:
        title = "EDIT MACHINE" if self._editing else "ADD MACHINE"
        with Vertical(id="form-card"):
            yield Static(f"◆ {title} ◆", id="form-title")
            yield from self._row("Name", "name", self._initial.name if self._initial else "")
            yield from self._row(
                "Serial Port",
                "port",
                self._initial.port if self._initial else "",
                placeholder="/dev/ttyUSB0 (blank = autodetect)",
            )
            yield from self._row(
                "Baud",
                "baud",
                str(self._initial.baud if self._initial else 115200),
            )
            with Horizontal(classes="form-row"):
                yield Label("Units", classes="form-label")
                yield Select(
                    [("MM", "MM"), ("INCH", "INCH")],
                    value=self._initial.units if self._initial else "MM",
                    id="field-units",
                    classes="form-input",
                    allow_blank=False,
                )
            yield from self._row(
                "Safe Z (mm)", "safe_z", str(self._initial.safe_z if self._initial else 5.0),
            )
            yield from self._row(
                "Tool Ø (mm)", "tool_diameter",
                str(self._initial.tool_diameter if self._initial else 3.0),
            )
            yield from self._row(
                "Stock X / Y / Z",
                "stock",
                self._stock_str(),
                placeholder="100,100,20",
            )
            yield from self._row(
                "Notes", "notes", self._initial.notes if self._initial else "", placeholder="optional",
            )
            with Horizontal(id="form-buttons"):
                yield Button("Save", variant="primary", id="form-save")
                yield Button("Cancel", id="form-cancel")

    def _stock_str(self) -> str:
        if self._initial is None:
            return "100,100,20"
        return f"{self._initial.stock_x},{self._initial.stock_y},{self._initial.stock_z}"

    def _row(
        self,
        label: str,
        field: str,
        value: str,
        placeholder: str = "",
    ):
        with Horizontal(classes="form-row"):
            yield Label(label, classes="form-label")
            yield Input(value=value, placeholder=placeholder, id=f"field-{field}", classes="form-input")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "form-cancel":
            self.dismiss(None)
            return
        if event.button.id == "form-save":
            self._submit()

    def _submit(self) -> None:
        try:
            name = self.query_one("#field-name", Input).value.strip()
            if not name:
                self.app.notify("Name is required.", severity="error")
                return
            port = self.query_one("#field-port", Input).value.strip()
            baud = int(self.query_one("#field-baud", Input).value or "115200")
            units = self.query_one("#field-units", Select).value or "MM"
            safe_z = float(self.query_one("#field-safe_z", Input).value or "5")
            tool_d = float(self.query_one("#field-tool_diameter", Input).value or "3")
            stock = self.query_one("#field-stock", Input).value or "100,100,20"
            sx, sy, sz = (float(x.strip()) for x in stock.split(","))
            notes = self.query_one("#field-notes", Input).value
            profile = MachineProfile(
                name=name,
                port=port,
                baud=baud,
                units=str(units),
                safe_z=safe_z,
                tool_diameter=tool_d,
                stock_x=sx,
                stock_y=sy,
                stock_z=sz,
                notes=notes,
            )
            self.dismiss(profile)
        except (ValueError, TypeError) as exc:
            self.app.notify(f"Invalid input: {exc}", severity="error")


class MachinesScreen(Container):
    """Top-level machines screen — embedded inside a TabPane."""

    DEFAULT_CSS = """
    MachinesScreen {
        layout: vertical;
        padding: 1 2;
    }
    #machines-header {
        height: 1;
        content-align: center middle;
        color: #00d4ff;
        text-style: bold;
    }
    #machines-table {
        height: 1fr;
        margin-top: 1;
        border: round #a855f7;
    }
    #machines-buttons {
        height: 3;
        margin-top: 1;
        align: center middle;
    }
    #machines-detail {
        height: auto;
        max-height: 10;
        margin-top: 1;
        border: round #00d4ff;
        padding: 0 1;
        background: #181826;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("[ Saved Machines ]", id="machines-header")
        yield DataTable(id="machines-table", cursor_type="row", zebra_stripes=True)
        with Horizontal(id="machines-buttons"):
            yield Button("⚙ Add", variant="primary", id="btn-add")
            yield Button("✎ Edit", id="btn-edit")
            yield Button("✖ Delete", variant="error", id="btn-delete")
            yield Button("⚡ Set Active", id="btn-active")
            yield Button("🔌 Connect", variant="success", id="btn-connect")
            yield Button("⏏ Disconnect", id="btn-disconnect")
        yield Static("Select a machine to see details.", id="machines-detail")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Active", "Name", "Port", "Baud", "Units", "Tool Ø", "Stock X×Y×Z", "Notes")
        self._refresh()

    def _refresh(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        store = self._store()
        for p in store.profiles:
            mark = "●" if store.active == p.name else " "
            table.add_row(
                mark,
                p.name,
                p.port or "(auto)",
                str(p.baud),
                p.units,
                f"{p.tool_diameter:.2f}",
                f"{p.stock_x:g}×{p.stock_y:g}×{p.stock_z:g}",
                p.notes,
                key=p.name,
            )
        self._update_detail()

    def _store(self):
        app: DeuspyApp = self.app  # type: ignore[assignment]
        return app.store

    def _selected_name(self) -> str | None:
        table = self.query_one(DataTable)
        if table.cursor_row is None or table.cursor_row < 0 or table.cursor_row >= table.row_count:
            return None
        try:
            row_key = table.coordinate_to_cell_key((table.cursor_row, 0)).row_key
            return str(row_key.value) if row_key.value is not None else None
        except Exception:
            return None

    def _update_detail(self) -> None:
        from deuspy.machine import get_machine
        store = self._store()
        m = get_machine()
        connected = "[green]CONNECTED[/green]" if m.backends else "[red]disconnected[/red]"
        active = store.active or "(none)"
        sel = self._selected_name() or "(none)"
        text = (
            f"[#8080a0]Active profile:[/] [#00d4ff bold]{active}[/]    "
            f"[#8080a0]Machine state:[/] {connected}    "
            f"[#8080a0]Selected:[/] [#a855f7]{sel}[/]"
        )
        self.query_one("#machines-detail", Static).update(text)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._update_detail()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-add":
            await self._add()
        elif bid == "btn-edit":
            await self._edit()
        elif bid == "btn-delete":
            self._delete()
        elif bid == "btn-active":
            self._set_active()
        elif bid == "btn-connect":
            self._connect()
        elif bid == "btn-disconnect":
            self._disconnect()

    async def _add(self) -> None:
        result = await self.app.push_screen_wait(MachineForm())
        if result is None:
            return
        store = self._store()
        if store.get(result.name) is not None:
            self.app.notify(f"Profile {result.name!r} already exists.", severity="error")
            return
        store.upsert(result)
        store.save()
        self._refresh()
        self.app.notify(f"Added profile {result.name!r}.", severity="information")

    async def _edit(self) -> None:
        store = self._store()
        name = self._selected_name()
        if name is None:
            self.app.notify("Select a row first.", severity="warning")
            return
        existing = store.get(name)
        if existing is None:
            return
        result = await self.app.push_screen_wait(MachineForm(profile=existing))
        if result is None:
            return
        # Allow rename: drop the old, insert the new.
        if result.name != name:
            store.delete(name)
        store.upsert(result)
        store.save()
        self._refresh()
        self.app.notify(f"Updated {result.name!r}.")

    def _delete(self) -> None:
        store = self._store()
        name = self._selected_name()
        if name is None:
            self.app.notify("Select a row first.", severity="warning")
            return
        if store.delete(name):
            store.save()
            self._refresh()
            self.app.notify(f"Deleted {name!r}.", severity="warning")

    def _set_active(self) -> None:
        store = self._store()
        name = self._selected_name()
        if name is None:
            self.app.notify("Select a row first.", severity="warning")
            return
        store.active = name
        store.save()
        self._refresh()
        self.app.notify(f"Active profile: {name!r}.", severity="information")

    def _connect(self) -> None:
        from deuspy import api
        from deuspy.machine import Tool, get_machine
        from deuspy.units import INCH, MM, Vec3

        store = self._store()
        name = self._selected_name() or store.active
        if name is None:
            self.app.notify("Select or set an active profile first.", severity="warning")
            return
        profile = store.get(name)
        if profile is None:
            return

        m = get_machine()
        if m.backends:
            self.app.notify("Already connected. Disconnect first.", severity="warning")
            return

        try:
            api.connect(
                port=profile.port or None,
                baud=profile.baud,
                dry_run=not profile.port,  # blank port → dry-run
                visualize=False,
            )
            api.set_units(MM if profile.units == "MM" else INCH)
            api.set_safe_z(profile.safe_z)
            api.set_tool(Tool(diameter=profile.tool_diameter))
            api.set_stock(Vec3(profile.stock_x, profile.stock_y, profile.stock_z))
            store.active = name
            store.save()
            self._refresh()
            mode = "DRY-RUN" if not profile.port else "HARDWARE"
            self.app.notify(f"Connected to {name!r} ({mode}).", severity="information")
        except Exception as exc:  # noqa: BLE001
            self.app.notify(f"Connect failed: {exc}", severity="error")

    def _disconnect(self) -> None:
        from deuspy import api
        try:
            api.disconnect()
            self._refresh()
            self.app.notify("Disconnected.", severity="warning")
        except Exception as exc:  # noqa: BLE001
            self.app.notify(f"Disconnect failed: {exc}", severity="error")
