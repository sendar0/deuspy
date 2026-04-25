"""Default values and tunable knobs."""

from __future__ import annotations

DEFAULT_BAUD = 115200
DEFAULT_FEED = 100.0          # current units/min
DEFAULT_SAFE_Z = 5.0          # mm (relative to WCS origin)
DEFAULT_TOOL_DIAMETER = 3.0   # mm
DEFAULT_TOOL_FLUTES = 2

POLL_INTERVAL_S = 0.2         # GRBL `?` cadence during motion
ACK_TIMEOUT_S = 30.0          # how long to wait for `ok` before giving up
SERIAL_RW_TIMEOUT_S = 1.0
