"""DryRun backend: captures G-code, simulates state, prints to stdout."""

from __future__ import annotations

import re
import sys
from typing import TextIO

from deuspy.backends.base import BackendResult, MachineStatus
from deuspy.units import ORIGIN, Vec3

_AXIS_RE = re.compile(r"([XYZF])([-+]?\d*\.?\d+)")


class DryRunBackend:
    """A backend that doesn't touch hardware: it logs every line and tracks position.

    Useful as a safe default and for the test suite (golden-file comparisons of
    emitted G-code).
    """

    name = "dryrun"

    def __init__(self, *, stream: TextIO | None = sys.stdout, echo: bool = True) -> None:
        self._stream = stream
        self._echo = echo
        self.lines: list[str] = []
        self._position = ORIGIN
        self._absolute = True
        self._feed = 0.0
        self._spindle = 0.0
        self._state = "Idle"

    def is_authoritative(self) -> bool:
        return True

    def send(self, line: str, *, blocking: bool = True) -> BackendResult:
        del blocking  # DryRun is always synchronous-ish.
        self.lines.append(line)
        if self._echo and self._stream is not None:
            self._stream.write(f"[dryrun] {line}\n")
            self._stream.flush()
        self._apply(line)
        return BackendResult(ok=True, raw="ok")

    def status(self) -> MachineStatus:
        return MachineStatus(
            state=self._state,
            mpos=self._position,
            wpos=self._position,
            buffer_free=15,
            feed=self._feed,
            spindle=self._spindle,
        )

    def stop(self, *, soft: bool = True) -> None:
        self._state = "Hold" if soft else "Idle"

    def close(self) -> None:
        pass

    # --- simulation helpers -------------------------------------------------

    def _apply(self, line: str) -> None:
        head = line.split(maxsplit=1)[0] if line else ""
        if head == "G90":
            self._absolute = True
            return
        if head == "G91":
            self._absolute = False
            return
        if head in ("G0", "G1"):
            self._update_position(line)
            return
        if head == "M3" or head == "M4":
            m = re.search(r"S([-+]?\d*\.?\d+)", line)
            if m:
                self._spindle = float(m.group(1))
            return
        if head == "M5":
            self._spindle = 0.0
            return
        # Other commands (G20/G21/$H/etc.) leave position alone.

    def _update_position(self, line: str) -> None:
        x = y = z = None
        for axis, val in _AXIS_RE.findall(line):
            v = float(val)
            if axis == "X":
                x = v
            elif axis == "Y":
                y = v
            elif axis == "Z":
                z = v
            elif axis == "F":
                self._feed = v
        if self._absolute:
            self._position = self._position.with_(
                x=self._position.x if x is None else x,
                y=self._position.y if y is None else y,
                z=self._position.z if z is None else z,
            )
        else:
            self._position = Vec3(
                self._position.x + (x or 0.0),
                self._position.y + (y or 0.0),
                self._position.z + (z or 0.0),
            )
