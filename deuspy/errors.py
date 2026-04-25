"""Exception hierarchy."""

from __future__ import annotations


class CncError(Exception):
    """Base exception for all deuspy errors."""


class ConnectionLost(CncError):
    """The serial link to the controller is no longer usable."""


class AlarmError(CncError):
    """GRBL has entered an alarm state. User must `unlock()` before continuing."""

    def __init__(self, code: int | None, message: str = "") -> None:
        self.code = code
        super().__init__(message or f"GRBL alarm {code}")


class GrblError(CncError):
    """GRBL responded `error:N` to a command."""

    def __init__(self, code: int, line: str = "") -> None:
        self.code = code
        self.line = line
        super().__init__(f"GRBL error:{code} on line: {line!r}")


class BackendDisagreement(CncError):
    """Authoritative and non-authoritative backends report inconsistent state."""


class NotConnectedError(CncError):
    """Operation requires an active connection."""
