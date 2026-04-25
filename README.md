# deuspy

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

## What's in v1

`Box` shape + `Pocket`/`Perimeter`/`Engrave` strategies (single tool, flat endmill, manual safe-Z); blocking dispatch; status polling; pyvista visualizer; alarm/feed-hold/soft-reset paths; single G54 work coordinate system.

Stubbed for v2: arc moves (G2/G3), other shapes (Cylinder, Hole, Polyline), DXF/SVG import, probing, tool changes, multi-WCS, async streaming `Job` handles, character-counting streamer.

## Running the tests

```bash
uv pip install -e '.[viz,dev]'
uv run pytest
```

The acceptance gate is `tests/test_dryrun_session.py` — it replays the example session above and checks the emitted G-code.
