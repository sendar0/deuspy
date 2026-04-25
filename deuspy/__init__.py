"""deuspy — interactive GRBL CNC control from a Python REPL."""

from deuspy.api import (
    change_tool,
    connect,
    disconnect,
    execute,
    home,
    move,
    probe,
    select_wcs,
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
from deuspy.errors import AlarmError, CncError, ConnectionLost, GrblError
from deuspy.job import Job
from deuspy.machine import Tool
from deuspy.shapes import Box, Cylinder, Hole, Polyline, Shape
from deuspy.strategies import Engrave, PeckDrill, Perimeter, Pocket, Strategy
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
    "Job",
    # shapes
    "Shape",
    "Box",
    "Cylinder",
    "Hole",
    "Polyline",
    # strategies
    "Strategy",
    "Pocket",
    "Perimeter",
    "Engrave",
    "PeckDrill",
    # toolpath
    "Move",
    "Toolpath",
    # errors
    "CncError",
    "AlarmError",
    "ConnectionLost",
    "GrblError",
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
    "select_wcs",
    "set_safe_z",
    "set_tool",
    "set_stock",
    "stop",
    "status",
    "unlock",
    "change_tool",
    "probe",
]
