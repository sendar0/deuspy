"""Job: handle for a streaming toolpath execution."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class Job:
    """Async handle for a streamed toolpath.

    Created by `execute(..., blocking=False)`. The caller can:
      - `wait(timeout=None)`: block until the job finishes (or timeout).
      - `progress() -> (sent, total)`: peek at how far we've gotten.
      - `cancel()`: request the backend to feed-hold + soft-reset and stop pushing.
      - `done`: True once the streamer thread has exited.
      - `error`: non-None if streaming raised.
    """

    total_lines: int = 0
    _sent: int = 0
    _completed: int = 0
    _error: Exception | None = None
    _cancelled: bool = False
    _done_event: threading.Event = field(default_factory=threading.Event)
    _thread: threading.Thread | None = None

    def wait(self, timeout: float | None = None) -> bool:
        """Block until the job finishes; returns True if done, False on timeout."""
        return self._done_event.wait(timeout)

    def progress(self) -> tuple[int, int]:
        """Return (lines_sent, total_lines). 'sent' includes lines awaiting `ok`."""
        return self._sent, self.total_lines

    def acked(self) -> int:
        """Number of lines GRBL has acknowledged (completed)."""
        return self._completed

    def cancel(self) -> None:
        """Request cancellation. The streamer will feed-hold and soft-reset."""
        self._cancelled = True

    @property
    def done(self) -> bool:
        return self._done_event.is_set()

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    @property
    def error(self) -> Exception | None:
        return self._error

    # --- streamer-side helpers ---

    def _mark_sent(self) -> None:
        self._sent += 1

    def _mark_acked(self) -> None:
        self._completed += 1

    def _finish(self, error: Exception | None = None) -> None:
        self._error = error
        self._done_event.set()
