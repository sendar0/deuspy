"""deuspy — interactive GRBL CNC control from a Python REPL."""

from deuspy.api import (
    connect,
    disconnect,
    execute,
    home,
    move,
    set_movement_speed,
    set_origin,
    set_safe_z,
    set_spindle_speed,
    set_stock,
    set_tool,
    set_units,
    status,
    stop,
    unlock,
)
from deuspy.errors import AlarmError, CncError, ConnectionLost
from deuspy.machine import Tool
from deuspy.shapes import Box, Shape
from deuspy.strategies import Engrave, Perimeter, Pocket, Strategy
from deuspy.toolpath import Move, Toolpath
from deuspy.units import CCW, CW, INCH, MM, ORIGIN, Unit, Vec3

origin = ORIGIN

__all__ = [
    # constants
    "MM",
    "INCH",
    "ORIGIN",
    "origin",
    "CW",
    "CCW",
    # types
    "Unit",
    "Vec3",
    "Tool",
    "Shape",
    "Box",
    "Strategy",
    "Pocket",
    "Perimeter",
    "Engrave",
    "Move",
    "Toolpath",
    # errors
    "CncError",
    "AlarmError",
    "ConnectionLost",
    # API
    "connect",
    "disconnect",
    "move",
    "execute",
    "home",
    "set_units",
    "set_movement_speed",
    "set_spindle_speed",
    "set_origin",
    "set_safe_z",
    "set_tool",
    "set_stock",
    "stop",
    "status",
    "unlock",
]
