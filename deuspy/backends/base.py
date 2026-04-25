"""Backend Protocol and shared dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from deuspy.units import Vec3


@dataclass(frozen=True)
class BackendResult:
    ok: bool
    raw: str = ""
    error_code: int | None = None


@dataclass(frozen=True)
class MachineStatus:
    """Snapshot of controller state. Mirrors GRBL's status report fields."""

    state: str          # "Idle", "Run", "Hold", "Alarm", "Home", "Check", "Door", "Sleep"
    mpos: Vec3          # machine coordinates
    wpos: Vec3          # work coordinates (relative to active WCS)
    buffer_free: int    # planner blocks free (Bf)
    feed: float = 0.0
    spindle: float = 0.0


@runtime_checkable
class Backend(Protocol):
    """The contract every backend (DryRun, GRBL, Visualizer) implements."""

    name: str

    def is_authoritative(self) -> bool:
        """True for backends that own machine state (GRBL real, DryRun in dry mode).

        At most one authoritative backend may be registered at a time.
        """

    def send(self, line: str, *, blocking: bool = True) -> BackendResult:
        """Send a single G-code line. If blocking, wait for ack; otherwise return immediately."""

    def status(self) -> MachineStatus:
        """Return the latest machine status."""

    def stop(self, *, soft: bool = True) -> None:
        """Halt motion. soft=True is feed-hold; soft=False is hard-reset."""

    def close(self) -> None:
        """Release any held resources (serial port, viewer window, etc.)."""
