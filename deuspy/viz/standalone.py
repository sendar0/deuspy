"""Standalone 3D viewer — runs in its own process so X11/Qt errors can't kill the TUI.

Usage:
    python -m deuspy.viz.standalone <path-to-gcode-file>

The TUI launches this as a subprocess with the toolpath written to a temp file.
This module uses `pyvista.Plotter` directly (not pyvistaqt) — `.show()` blocks
on the Qt event loop until the user closes the window, which is the desired
behaviour for a one-shot viewer.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_AXIS_RE = re.compile(r"([XYZ])([-+]?\d*\.?\d+)")


def _parse_toolpath(lines: list[str]) -> tuple[list[tuple[float, float, float]], list[str]]:
    """Walk G0/G1/G2/G3 lines and return ([(x,y,z)…], [kind…])."""
    pts: list[tuple[float, float, float]] = []
    kinds: list[str] = []
    x = y = z = 0.0
    absolute = True
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        head = line.split(maxsplit=1)[0]
        if head == "G90":
            absolute = True
            continue
        if head == "G91":
            absolute = False
            continue
        if head not in ("G0", "G1", "G2", "G3"):
            continue
        nx = ny = nz = None
        for axis, val in _AXIS_RE.findall(line):
            v = float(val)
            if axis == "X":
                nx = v
            elif axis == "Y":
                ny = v
            elif axis == "Z":
                nz = v
        if absolute:
            if nx is not None:
                x = nx
            if ny is not None:
                y = ny
            if nz is not None:
                z = nz
        else:
            x += nx or 0.0
            y += ny or 0.0
            z += nz or 0.0
        pts.append((x, y, z))
        kinds.append(head)
    return pts, kinds


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m deuspy.viz.standalone <gcode-file>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    if not path.exists():
        print(f"file not found: {path}", file=sys.stderr)
        return 1

    try:
        import numpy as np
        import pyvista as pv
    except ImportError as exc:
        print(f"viewer unavailable: {exc}", file=sys.stderr)
        return 1

    pts, kinds = _parse_toolpath(path.read_text().splitlines())
    if not pts:
        print("no motion in toolpath", file=sys.stderr)
        return 1

    plotter = pv.Plotter(title="deuspy — toolpath", window_size=(1200, 800))
    plotter.add_axes()
    plotter.show_grid()
    plotter.set_background("#0a0a14")

    # Build line segments grouped by kind for colour.
    feeds: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
    rapids: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
    arcs: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
    for i in range(1, len(pts)):
        a, b = pts[i - 1], pts[i]
        kind = kinds[i]
        if kind == "G0":
            rapids.append((a, b))
        elif kind in ("G2", "G3"):
            arcs.append((a, b))
        else:
            feeds.append((a, b))

    def _add_segments(segs, color, width):
        if not segs:
            return
        # Build vertex array + line cells in pyvista's "padded" format.
        verts = []
        cells = []
        idx = 0
        for a, b in segs:
            verts.extend([a, b])
            cells.extend([2, idx, idx + 1])
            idx += 2
        mesh = pv.PolyData(np.asarray(verts, dtype=float))
        mesh.lines = np.asarray(cells, dtype=int)
        plotter.add_mesh(mesh, color=color, line_width=width)

    _add_segments(rapids, "#4a4a6a", 1)
    _add_segments(feeds, "#00d4ff", 3)
    _add_segments(arcs, "#a855f7", 3)

    # Mark the start (green) and end (magenta) for orientation.
    plotter.add_mesh(pv.Sphere(radius=0.5, center=pts[0]), color="#00ff88")
    plotter.add_mesh(pv.Sphere(radius=0.5, center=pts[-1]), color="#ff00aa")

    plotter.show()  # blocks until user closes the window
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
