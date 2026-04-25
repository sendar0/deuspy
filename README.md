# deuspy

> ⚠️ **WARNING — highly experimental, untested, unfinished, and largely non-functional.** Do **not** point this at a real CNC machine you care about. Coordinate systems, feeds, and toolpaths have not been validated against hardware. Use at your own risk; expect bugs, crashes, missing features, and unsafe G-code. Treat every output as suspect.

*deus py machina* — interactive control of a [GRBL](https://github.com/gnea/grbl) CNC machine from a Python REPL. The goal is the ergonomics of a manual machine: type a command, the head moves.

## Install

This project uses [uv](https://docs.astral.sh/uv/) for environment management.

```bash
# Create a venv and install in editable mode (basic, no visualizer)
uv venv
uv pip install -e .

# With 3D toolpath viewer
uv pip install -e '.[viz]'

# Development (tests + lint)
uv pip install -e '.[viz,dev]'
```

Activate the venv with `source .venv/bin/activate`, or prefix commands with `uv run` (e.g. `uv run pytest`).

## TUI

A Textual-based terminal UI ships with the package:

```bash
uv run deuspy-tui
```

It opens with an animated splash, then a tabbed shell:

- **Machines** — add / edit / delete saved machine profiles (persisted to `~/.config/deuspy/machines.json`), set an active profile, connect / disconnect.
- **Designer** — pick a shape (Box, Cylinder, Hole, Star, Polyline rectangle) and a strategy (Pocket / Perimeter / Engrave / PeckDrill); dry-run and see an ASCII top-down toolpath preview with stats; "3D View" launches the pyvista 3D viewer in a Qt window.
- **REPL** — live machine state panel, command history, full Python REPL with the `deuspy` API pre-imported as `d`, plus quick-action buttons (Home, Origin, Center, Stop, Set Stock, Tool, Unlock) and a jog pad with X±/Y±/Z± and step-size control.

Keys: `1` / `2` / `3` switch tabs · `q` quits · `?` help.

## Quick start

```python
>>> from deuspy import *
>>> connect(dry_run=True)            # or connect("/dev/ttyUSB0") for real hardware
>>> set_units(MM)
>>> set_movement_speed(100)
>>> move(origin)
>>> move(x=2, y=2)
>>> set_spindle_speed(12000)
>>> box = Box(length=4, width=2, height=4)
>>> execute(box)                     # default Pocket strategy
>>> set_spindle_speed(0)
>>> disconnect()
```

## Concepts

- **Geometry** (`Box`, …) is pure data. It knows nothing about cutting.
- **Strategy** (`Pocket`, `Perimeter`, `Engrave`) turns geometry + machine state into a `Toolpath`. Pluggable per call:
  ```python
  execute(box)                                       # default Pocket
  execute(box, Perimeter(stepdown=0.5))              # outline cut
  execute(box, Engrave(depth=0.2))                   # surface trace
  ```
- **Backends** consume G-code. Currently:
  - `DryRunBackend` — captures G-code, simulates state, no hardware.
  - `GrblBackend` — pyserial-based, real GRBL streaming.
  - `PyVistaBackend` — non-authoritative; live 3D + top-down viewer.

  Multiple backends can be active at once. The visualizer fans out alongside the real GRBL link automatically.

## Manual-machine semantics

- Commands **block by default**. `move(...)` returns only after GRBL reports `Idle` and the planner buffer is empty. The REPL prompt waits — like jogging a manual mill.
- XY-only moves keep the current Z. To lift, pass `z=` explicitly (or use `rapid=True`).
- Pass `blocking=False` to stream into GRBL's planner buffer for long jobs.

## Safety

- **Ctrl-C** during a blocking move issues a feed-hold (`!`) immediately, then re-raises so the prompt returns. Resume with `unlock()` after clearing the cause.
- An `ALARM:N` from the controller raises `AlarmError`; **the library never auto-clears alarms**. Investigate, then call `unlock()`.
- `stop(soft=True)` is a feed-hold; `stop(soft=False)` is a soft-reset that requires re-`connect()`.

## Running the tests

```bash
uv pip install -e '.[viz,dev]'
uv run pytest
```

The acceptance gate is `tests/test_dryrun_session.py` — it replays the example session above and checks the emitted G-code.
