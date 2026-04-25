"""ASCII top-down toolpath preview."""

from __future__ import annotations

from textual.widgets import Static

from deuspy.toolpath import Toolpath


def _render_ascii(tp: Toolpath, width: int = 60, height: int = 24) -> str:
    """Render a top-down (XY) view of a toolpath as monospace art."""
    if len(tp) == 0:
        return "[#8080a0](empty toolpath)[/]"

    xs = [m.target.x for m in tp.moves]
    ys = [m.target.y for m in tp.moves]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    dx = max(x_max - x_min, 1e-6)
    dy = max(y_max - y_min, 1e-6)

    grid: list[list[str]] = [[" "] * width for _ in range(height)]
    colors: list[list[str]] = [["#4a4a6a"] * width for _ in range(height)]

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
                        ch, col = "·", "#4a4a6a"
                    elif m.kind in ("G2", "G3"):
                        ch, col = "•", "#a855f7"
                    else:
                        ch, col = "█", "#00d4ff"
                    grid[y][x] = ch
                    colors[y][x] = col
        if 0 <= cy < height and 0 <= cx < width:
            grid[cy][cx] = "◉"
            colors[cy][cx] = "#ff00aa"
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
        border: round #00d4ff;
        background: #0a0a14;
        padding: 0 1;
        content-align: center middle;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__("[#8080a0](preview pending)[/]", **kwargs)
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
        return "[#8080a0](empty)[/]"
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
        f"[#8080a0]moves[/] [#00d4ff]{len(tp)}[/] · "
        f"[#8080a0]G0[/] [#a855f7]{rapids}[/] · "
        f"[#8080a0]G1[/] [#00ff88]{feeds}[/] · "
        f"[#8080a0]arcs[/] [#fbbf24]{arcs}[/] · "
        f"[#8080a0]cut[/] [#ff00aa]{dist:.2f}[/] · "
        f"[#8080a0]bbox[/] [#00d4ff]{max(xs)-min(xs):.1f}×{max(ys)-min(ys):.1f}×{max(zs)-min(zs):.1f}[/]"
    )
