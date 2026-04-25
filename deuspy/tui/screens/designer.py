"""Designer tab: build shapes, dry-run, preview the toolpath."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Input, Label, Select, Static

from deuspy.shapes import Box, Cylinder, Hole, Polyline
from deuspy.strategies import Engrave, PeckDrill, Perimeter, Pocket
from deuspy.strategies.base import MachineContext
from deuspy.tui.widgets.toolpath_view import ToolpathView, toolpath_stats
from deuspy.units import ORIGIN

SHAPES = [
    ("Box", "box"),
    ("Cylinder", "cylinder"),
    ("Hole", "hole"),
    ("Star", "star"),
    ("Rectangle (Polyline)", "polyrect"),
]
STRATEGIES = [
    ("Pocket", "pocket"),
    ("Perimeter", "perimeter"),
    ("Engrave", "engrave"),
    ("PeckDrill", "peckdrill"),
]


class DesignerScreen(Container):
    """Define a shape + strategy, dry-run, see the resulting toolpath."""

    DEFAULT_CSS = """
    DesignerScreen {
        layout: grid;
        grid-size: 2 1;
        grid-columns: 42 1fr;
        grid-gutter: 0 2;
        padding: 1 2;
    }
    #designer-form {
        layout: vertical;
        border: round $surface;
        background: $surface;
        padding: 0 1;
    }
    #designer-form:focus-within { border: round cyan; }
    #designer-preview {
        layout: grid;
        grid-size: 1 2;
        grid-rows: 3 1fr;
        grid-gutter: 1 0;
    }
    .form-row {
        layout: horizontal;
        height: 3;
    }
    .form-label {
        width: 14;
        color: $text-muted;
        padding: 1 1;
    }
    .form-input { width: 1fr; }
    .form-divider {
        color: $text-muted;
        text-style: italic;
        margin: 1 0 0 0;
    }
    #designer-actions {
        height: 3;
        align: center middle;
    }
    #designer-stats {
        content-align: center middle;
        background: $boost;
        border: round $surface;
        padding: 1 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="designer-form"):
            yield Static("◆ SHAPE BUILDER ◆", classes="panel-title")
            with Horizontal(classes="form-row"):
                yield Label("Shape", classes="form-label")
                yield Select(SHAPES, value="box", id="sel-shape", classes="form-input", allow_blank=False)
            with Horizontal(classes="form-row"):
                yield Label("Strategy", classes="form-label")
                yield Select(
                    STRATEGIES, value="pocket", id="sel-strategy", classes="form-input", allow_blank=False,
                )
            yield Static("── shape parameters ──", classes="form-divider")
            with Horizontal(classes="form-row"):
                yield Label("p1", classes="form-label", id="lbl-p1")
                yield Input(value="10", id="in-p1", classes="form-input")
            with Horizontal(classes="form-row"):
                yield Label("p2", classes="form-label", id="lbl-p2")
                yield Input(value="10", id="in-p2", classes="form-input")
            with Horizontal(classes="form-row"):
                yield Label("p3", classes="form-label", id="lbl-p3")
                yield Input(value="2", id="in-p3", classes="form-input")
            with Horizontal(classes="form-row"):
                yield Label("p4", classes="form-label", id="lbl-p4")
                yield Input(value="5", id="in-p4", classes="form-input")
            yield Static("── cutting context ──", classes="form-divider")
            with Horizontal(classes="form-row"):
                yield Label("Tool Ø", classes="form-label")
                yield Input(value="3.0", id="in-tool", classes="form-input")
            with Horizontal(classes="form-row"):
                yield Label("Feed", classes="form-label")
                yield Input(value="100", id="in-feed", classes="form-input")
            with Horizontal(classes="form-row"):
                yield Label("Safe Z", classes="form-label")
                yield Input(value="5", id="in-safez", classes="form-input")
            with Horizontal(id="designer-actions"):
                yield Button("⏵ Dry Run", variant="primary", id="btn-preview")
                yield Button("◉ 3D View", variant="success", id="btn-3d")
                yield Button("⧉ Copy G", id="btn-copy")
        with Vertical(id="designer-preview"):
            yield Static("[dim](preview pending — press Dry Run)[/]", id="designer-stats")
            yield ToolpathView(id="designer-toolpath")

    def on_mount(self) -> None:
        self._update_labels()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "sel-shape":
            self._update_labels()
        elif event.select.id == "sel-strategy" and event.value == "peckdrill":
            # PeckDrill only makes sense for holes — switch the shape selector.
            self.query_one("#sel-shape", Select).value = "hole"
            self._update_labels()

    def _update_labels(self) -> None:
        shape = self.query_one("#sel-shape", Select).value
        labels = {
            "box":      [("Length", "10"), ("Width", "10"), ("Height", "2"), ("(unused)", "0")],
            "cylinder": [("Radius", "5"), ("Height", "2"), ("(unused)", "0"), ("(unused)", "0")],
            "hole":     [("Diameter", "4"), ("Depth", "5"), ("(unused)", "0"), ("(unused)", "0")],
            "star":     [("Outer R", "10"), ("Inner R", "4"), ("Depth", "1"), ("Points", "5")],
            "polyrect": [("Length", "10"), ("Width", "6"), ("Depth", "2"), ("(unused)", "0")],
        }
        rows = labels.get(shape or "box", labels["box"])
        for i, (label, default) in enumerate(rows, start=1):
            self.query_one(f"#lbl-p{i}", Label).update(label)
            inp = self.query_one(f"#in-p{i}", Input)
            inp.disabled = label.startswith("(")
            if label.startswith("("):
                inp.value = "0"
            elif inp.value in ("0", ""):
                inp.value = default

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-preview":
            self._run_preview()
        elif bid == "btn-3d":
            self._launch_3d()
        elif bid == "btn-copy":
            self._copy_gcode()

    # ---- core ---------------------------------------------------------------

    def _build_shape(self):
        sh = self.query_one("#sel-shape", Select).value
        p = [self._float(f"#in-p{i}") for i in range(1, 5)]
        if sh == "box":
            return Box(length=p[0], width=p[1], height=p[2])
        if sh == "cylinder":
            return Cylinder(radius=p[0], height=p[1])
        if sh == "hole":
            return Hole(diameter=p[0], depth=p[1])
        if sh == "star":
            return Polyline.star(
                outer_radius=p[0], inner_radius=p[1], depth=p[2],
                points=int(p[3]) if p[3] >= 3 else 5,
            )
        if sh == "polyrect":
            return Polyline.rectangle(length=p[0], width=p[1], depth=p[2])
        raise ValueError(f"unknown shape {sh}")

    def _build_strategy(self):
        s = self.query_one("#sel-strategy", Select).value
        if s == "pocket":
            return Pocket()
        if s == "perimeter":
            # Polyline doesn't support nonzero offset yet — set offset=0 explicitly.
            sh = self.query_one("#sel-shape", Select).value
            if sh in ("star", "polyrect"):
                return Perimeter(offset=0)
            return Perimeter()
        if s == "engrave":
            return Engrave(depth=0.3)
        if s == "peckdrill":
            return PeckDrill()
        raise ValueError(f"unknown strategy {s}")

    def _float(self, sel: str) -> float:
        try:
            return float(self.query_one(sel, Input).value or "0")
        except ValueError:
            return 0.0

    def _ctx(self) -> MachineContext:
        return MachineContext(
            position=ORIGIN,
            safe_z=self._float("#in-safez"),
            feed=self._float("#in-feed"),
            tool_diameter=self._float("#in-tool"),
        )

    def _run_preview(self) -> None:
        try:
            shape = self._build_shape()
            strategy = self._build_strategy()
            tp = strategy.plan(shape, self._ctx())
        except Exception as exc:  # noqa: BLE001
            self.app.notify(f"Plan failed: {exc}", severity="error")
            return
        self._last_tp = tp
        self._last_shape = shape
        self.query_one("#designer-stats", Static).update(toolpath_stats(tp))
        self.query_one(ToolpathView).show(tp)
        self.app.notify(f"Generated {len(tp)} moves.", severity="information")

    def _launch_3d(self) -> None:
        """Spawn the 3D viewer in a subprocess.

        Running pyvistaqt inside the Textual process tends to crash the whole
        thing on X11 (BadWindow), since Qt and the asyncio loop fight over the
        display. A subprocess gives Qt its own X connection and isolates errors.
        """
        if not getattr(self, "_last_tp", None):
            self.app.notify("Run Dry Run first.", severity="warning")
            return

        import subprocess
        import sys
        import tempfile
        from pathlib import Path

        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".gcode", prefix="deuspy-viz-", delete=False
            ) as fh:
                for line in self._last_tp.iter_gcode():
                    fh.write(line + "\n")
                tmp_name = fh.name
            log_path = Path(tmp_name).with_suffix(".log")
            log_fh = log_path.open("w")  # noqa: SIM115 — handed to the subprocess
            subprocess.Popen(
                [sys.executable, "-m", "deuspy.viz.standalone", tmp_name],
                stdout=log_fh,
                stderr=log_fh,
                start_new_session=True,
            )
            self.app.notify(
                f"3D viewer launched · log: {log_path}",
                severity="information",
                timeout=8,
            )
        except Exception as exc:  # noqa: BLE001
            self.app.notify(f"3D viewer failed: {exc}", severity="error")

    def _copy_gcode(self) -> None:
        if not getattr(self, "_last_tp", None):
            self.app.notify("Run Dry Run first.", severity="warning")
            return
        text = "\n".join(self._last_tp.iter_gcode())
        try:
            self.app.copy_to_clipboard(text)
            self.app.notify(f"Copied {len(self._last_tp)} G-code lines.", severity="information")
        except Exception as exc:  # noqa: BLE001
            self.app.notify(f"Clipboard not available: {exc}", severity="warning")
