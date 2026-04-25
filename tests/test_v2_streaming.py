"""Async Job + character-counting streamer tests."""

from __future__ import annotations

import time

import pytest

from deuspy import (
    Box,
    Tool,
    connect,
    disconnect,
    execute,
    set_tool,
    set_units,
)
from deuspy.backends.dryrun import DryRunBackend
from deuspy.backends.grbl import GRBL_RX_BUFFER, GrblBackend
from deuspy.job import Job
from deuspy.units import MM


def test_dryrun_streaming_completes_synchronously():
    backend = DryRunBackend(echo=False)
    job = Job()
    backend.stream(["G21", "G90", "G0 X1 Y2 Z3", "M5"], job)
    assert job.done
    assert job.error is None
    assert job.progress() == (4, 4)
    assert job.acked() == 4


def test_dryrun_streaming_respects_cancel():
    backend = DryRunBackend(echo=False)
    job = Job()
    job._cancelled = True
    backend.stream(["G21", "G0 X1"], job)
    assert job.done
    assert job.progress()[0] == 0


def test_execute_blocking_false_returns_job(monkeypatch):
    """Plumbing test: blocking=False returns (Toolpath, Job) and the Job completes."""
    connect(dry_run=True, visualize=False)
    set_tool(Tool(diameter=1.0))
    set_units(MM)
    box = Box(length=4, height=2, width=4)
    result = execute(box, blocking=False)
    assert isinstance(result, tuple)
    tp, job = result
    assert isinstance(job, Job)
    assert job.wait(timeout=5.0)
    assert job.error is None
    assert job.progress()[1] > 0
    disconnect()


# --- GRBL streamer with FakeSerial -----------------------------------------


class FakeSerial:
    """Serial double sized to match GRBL's character-counting protocol."""

    def __init__(self, *, immediate_ok: bool = True) -> None:
        self._rx = bytearray()
        self._tx = bytearray()
        self._immediate_ok = immediate_ok
        self.dtr = True

    def write(self, data: bytes) -> int:
        self._tx.extend(data)
        if data == b"?":
            self._rx.extend(b"<Idle|MPos:0.0,0.0,0.0|Bf:15,128|FS:0,0>\r\n")
        elif data in (b"!", b"\x18"):
            pass  # realtime, no ack
        elif data.endswith(b"\n") and self._immediate_ok:
            self._rx.extend(b"ok\r\n")
        return len(data)

    def read(self, n: int) -> bytes:
        # Block briefly so the streamer can poll without busy-looping.
        deadline = time.monotonic() + 0.05
        while time.monotonic() < deadline:
            if self._rx:
                out = bytes(self._rx[:n])
                del self._rx[:n]
                return out
            time.sleep(0.005)
        return b""

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass

    @property
    def written(self) -> bytes:
        return bytes(self._tx)


def _make_grbl(fake: FakeSerial) -> GrblBackend:
    g = GrblBackend(port="/dev/null")
    g._ser = fake
    g._opened = True
    g._max_buffer_free = 15
    return g


def test_grbl_streamer_pushes_all_lines():
    fake = FakeSerial()
    grbl = _make_grbl(fake)
    job = Job()
    lines = [f"G1 X{i} Y0 F100" for i in range(20)]
    grbl.stream(lines, job)
    assert job.wait(timeout=5.0)
    assert job.error is None
    assert job.progress() == (20, 20)
    assert job.acked() == 20
    # All 20 lines should appear in the written byte stream.
    written = fake.written.decode("ascii")
    for i in range(20):
        assert f"G1 X{i} Y0 F100" in written


def test_grbl_streamer_respects_rx_buffer_limit():
    """Without acks, the streamer must pause once it hits the 128-byte ceiling."""
    fake = FakeSerial(immediate_ok=False)
    grbl = _make_grbl(fake)
    job = Job()
    # Each line is 17 bytes (incl. newline). 8 of them = 136 bytes — over the ceiling.
    lines = [f"G1 X{i:03d} Y000 F100" for i in range(8)]
    grbl.stream(lines, job)
    # Give the worker a chance to push what it can.
    time.sleep(0.2)
    sent, total = job.progress()
    assert sent < total, f"streamer should have paused on RX buffer; sent={sent}/{total}"
    # Now feed acks back to drain.
    fake._rx.extend(b"ok\r\n" * 8)
    assert job.wait(timeout=5.0)
    assert job.progress() == (8, 8)


def test_grbl_streamer_cancel_issues_feed_hold_and_reset():
    fake = FakeSerial(immediate_ok=False)
    grbl = _make_grbl(fake)
    job = Job()
    lines = [f"G1 X{i} Y0" for i in range(50)]
    grbl.stream(lines, job)
    time.sleep(0.05)
    job.cancel()
    # Provide enough acks for the streamer to notice cancel between iterations.
    fake._rx.extend(b"ok\r\n" * 10)
    assert job.wait(timeout=5.0)
    written = fake.written
    assert b"!" in written, "feed-hold should be issued on cancel"
    assert b"\x18" in written, "soft-reset should be issued on cancel"


def test_grbl_send_blocked_during_streaming():
    fake = FakeSerial(immediate_ok=False)
    grbl = _make_grbl(fake)
    job = Job()
    grbl.stream(["G1 X1 Y0", "G1 X2 Y0"], job)
    time.sleep(0.05)
    from deuspy.errors import ConnectionLost
    with pytest.raises(ConnectionLost):
        grbl.send("G21", blocking=False)
    fake._rx.extend(b"ok\r\nok\r\n")
    assert job.wait(timeout=5.0)


def test_grbl_streamer_propagates_grbl_error():
    fake = FakeSerial(immediate_ok=False)
    grbl = _make_grbl(fake)
    job = Job()
    grbl.stream(["BAD COMMAND"], job)
    fake._rx.extend(b"error:9\r\n")
    assert job.wait(timeout=5.0)
    from deuspy.errors import GrblError
    assert isinstance(job.error, GrblError)


def test_grbl_rx_buffer_constant():
    assert GRBL_RX_BUFFER == 128
