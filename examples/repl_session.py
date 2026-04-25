"""Example REPL session — paste into `python -i` to drive a (simulated) CNC.

Run as:
    python -i examples/repl_session.py

With dry_run=True, no hardware is touched; emitted G-code is printed to stdout.
"""

from deuspy import (
    MM,
    Box,
    Tool,
    connect,
    execute,
    move,
    origin,
    set_movement_speed,
    set_spindle_speed,
    set_tool,
    set_units,
)

# Connect in dry-run mode and (if pyvista is installed) pop up a viewer window.
connect(dry_run=True, visualize=False)

# A 1 mm endmill is small enough to clear the 2 mm-wide pocket below.
set_tool(Tool(diameter=1.0))

set_units(MM)
set_movement_speed(100)
move(origin)

# Approach the cut location.
move(x=2, y=2)

# Spin up the spindle — `12` is intentionally low so this is safe in simulation.
set_spindle_speed(12)

# Define a 4 × 2 mm pocket, 4 mm deep.
box = Box(length=4, height=4, width=2)

# Default strategy is Pocket. Override with `execute(box, Perimeter())` to cut the outline.
execute(box)

# Stop spindle and retract.
set_spindle_speed(0)
move(z=10, rapid=True)
