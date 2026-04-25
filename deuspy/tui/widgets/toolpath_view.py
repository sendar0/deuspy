"""ASCII top-down toolpath preview."""

from __future__ import annotations

from textual.widgets import Static

from deuspy.toolpath import Toolpath


def _render_ascii(tp: Toolpath, width: int = 60, height: int = 24) -> str:
    """Render a top-down (XY) view of a toolpath as monospace art."""
    if len(tp) == 0:
        return "[dim](empty toolpath)[/]"

    xs = [m.target.x for m in tp.moves]
    ys = [m.target.y for m in tp.moves]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    dx = max(x_max - x_min, 1e-6)
    dy = max(y_max - y_min, 1e-6)

    grid: list[list[str]] = [[" "] * width for _ in range(height)]
    colors: list[list[str]] = [["dim"] * width for _ in range(height)]

    def to_cell(x: float, y: float) -> tuple[int, int]:
        cx = int((x - x_min) / dx * (width - 1))
        # Invert Y so +Y goes up.
        cy = int((1 - (y - y_min) / dy) * (height - 1))
        return cx, cy

    px = py = None
    for m in tp.moves:
        cx, cy = to_cell(m.target.x, m.target.y)
        if px is not None and py is not None:
            # Bresenham-ish line draw.
            for x, y in _line(px, py, cx, cy):
                if 0 <= y < height and 0 <= x < width:
                    if m.kind == "G0":
                        ch, col = "·", "dim"
                    elif m.kind in ("G2", "G3"):
                        ch, col = "•", "yellow"
                    else:
                        ch, col = "█", "cyan"
                    grid[y][x] = ch
                    colors[y][x] = col
        if 0 <= cy < height and 0 <= cx < width:
            grid[cy][cx] = "◉"
            colors[cy][cx] = "magenta"
        px, py = cx, cy

    # Compose rich-coloured rows.
    lines: list[str] = []
    for row, crow in zip(grid, colors, strict=True):
        # Group runs of same colour for compactness.
        out = []
        cur_col = crow[0]
        run = ""
        for ch, col in zip(row, crow, strict=True):
            if col == cur_col:
                run += ch
            else:
                out.append(f"[{cur_col}]{_escape(run)}[/]")
                cur_col = col
                run = ch
        if run:
            out.append(f"[{cur_col}]{_escape(run)}[/]")
        lines.append("".join(out))
    return "\n".join(lines)


def _escape(s: str) -> str:
    return s.replace("[", r"\[")


def _line(x0: int, y0: int, x1: int, y1: int):
    """Bresenham's line algorithm — yields (x, y) cells."""
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        yield x, y
        if x == x1 and y == y1:
            return
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy


class ToolpathView(Static):
    """Static widget that renders a Toolpath as ASCII top-down art."""

    DEFAULT_CSS = """
    ToolpathView {
        border: round $surface;
        background: $background;
        padding: 0 1;
        content-align: center middle;
    }
    ToolpathView:focus-within { border: round cyan; }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__("[dim](preview pending)[/]", **kwargs)
        self._tp: Toolpath | None = None

    def show(self, tp: Toolpath) -> None:
        self._tp = tp
        # Compute a size that fits the widget, with sensible bounds.
        size = self.content_region
        w = max(40, min(size.width, 100))
        h = max(12, min(size.height, 30))
        self.update(_render_ascii(tp, width=w, height=h))


def toolpath_stats(tp: Toolpath) -> str:
    """One-line summary for a Toolpath."""
    if len(tp) == 0:
        return "[dim](empty)[/]"
    xs = [m.target.x for m in tp.moves]
    ys = [m.target.y for m in tp.moves]
    zs = [m.target.z for m in tp.moves]
    rapids = sum(1 for m in tp.moves if m.kind == "G0")
    feeds = sum(1 for m in tp.moves if m.kind == "G1")
    arcs = sum(1 for m in tp.moves if m.kind in ("G2", "G3"))
    # Cut distance = sum of feed/arc segments end-to-end (chord length for arcs).
    dist = 0.0
    px, py, pz = xs[0], ys[0], zs[0]
    for m in tp.moves[1:]:
        if m.kind != "G0":
            dist += ((m.target.x - px) ** 2 + (m.target.y - py) ** 2 + (m.target.z - pz) ** 2) ** 0.5
        px, py, pz = m.target.x, m.target.y, m.target.z
    return (
        f"[dim]moves[/] [cyan b]{len(tp)}[/] · "
        f"[dim]G0[/] [magenta]{rapids}[/] · "
        f"[dim]G1[/] [green]{feeds}[/] · "
        f"[dim]arcs[/] [yellow]{arcs}[/] · "
        f"[dim]cut[/] [cyan b]{dist:.2f}[/] · "
        f"[dim]bbox[/] [cyan]{max(xs)-min(xs):.1f}×{max(ys)-min(ys):.1f}×{max(zs)-min(zs):.1f}[/]"
    )
