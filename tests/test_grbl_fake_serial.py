"""GRBL backend tests using an in-process fake serial port."""

from __future__ import annotations

import threading
import time

import pytest

from deuspy.backends.grbl import GrblBackend, _parse_status
from deuspy.errors import AlarmError, GrblError


class FakeSerial:
    """Minimal serial-port double — implements just what GrblBackend uses."""

    def __init__(self, scripted_responses: list[bytes] | None = None) -> None:
        self._rx = bytearray()  # data we'll hand to .read()
        self._tx = bytearray()  # data the SUT has written
        self._lock = threading.Lock()
        self.dtr = True
        self._scripted = list(scripted_responses or [])

    # --- pyserial-compatible surface ---

    def write(self, data: bytes) -> int:
        with self._lock:
            self._tx.extend(data)
            # Default behaviour: any \n-terminated line gets a queued response,
            # otherwise the test enqueues responses manually.
            self._handle_write(data)
        return len(data)

    def read(self, n: int) -> bytes:
        deadline = time.monotonic() + 0.05
        while time.monotonic() < deadline:
            with self._lock:
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

    # --- test helpers ---

    def queue(self, payload: bytes) -> None:
        with self._lock:
            self._rx.extend(payload)

    @property
    def written(self) -> bytes:
        with self._lock:
            return bytes(self._tx)

    def _handle_write(self, data: bytes) -> None:
        # `?` → next scripted status (or a default Idle one).
        if data == b"?":
            if self._scripted:
                self._rx.extend(self._scripted.pop(0))
            else:
                self._rx.extend(b"<Idle|MPos:0.000,0.000,0.000|Bf:15,128|FS:0,0>\r\n")
            return
        # \x18 → soft reset, no immediate ack.
        if data == b"\x18" or data == b"!":
            return
        # Anything ending with \n → schedule an `ok\r\n`, except scripted overrides.
        if data.endswith(b"\n"):
            if self._scripted:
                self._rx.extend(self._scripted.pop(0))
            else:
                self._rx.extend(b"ok\r\n")


def _make_backend(fake: FakeSerial) -> GrblBackend:
    backend = GrblBackend(port="/dev/null", baud=115200)
    backend._ser = fake  # type: ignore[assignment]
    backend._opened = True
    backend._max_buffer_free = 15
    return backend


def test_parse_status_full():
    st = _parse_status("Idle|MPos:1.000,2.000,3.000|WPos:0.500,1.000,1.500|Bf:15,128|FS:100,2000")
    assert st.state == "Idle"
    assert st.mpos.x == 1.0 and st.mpos.y == 2.0 and st.mpos.z == 3.0
    assert st.wpos.x == 0.5
    assert st.buffer_free == 15
    assert st.feed == 100
    assert st.spindle == 2000


def test_send_simple_ok():
    fake = FakeSerial()
    grbl = _make_backend(fake)
    result = grbl.send("G21", blocking=False)
    assert result.ok
    assert b"G21\n" in fake.written


def test_send_motion_blocking_polls_for_idle():
    fake = FakeSerial(
        scripted_responses=[
            b"ok\r\n",  # ack for the G1
            b"<Run|MPos:0.0,0.0,0.0|Bf:5,128>\r\n",
            b"<Run|MPos:1.0,0.0,0.0|Bf:10,128>\r\n",
            b"<Idle|MPos:1.0,0.0,0.0|Bf:15,128>\r\n",
        ]
    )
    grbl = _make_backend(fake)
    result = grbl.send("G1 X1 F100", blocking=True)
    assert result.ok
    # The status query character `?` should have been written at least once.
    assert b"?" in fake.written


def test_send_error_raises_grbl_error():
    fake = FakeSerial(scripted_responses=[b"error:9\r\n"])
    grbl = _make_backend(fake)
    with pytest.raises(GrblError) as exc:
        grbl.send("BAD COMMAND", blocking=False)
    assert exc.value.code == 9


def test_send_alarm_raises_alarm_error():
    fake = FakeSerial(scripted_responses=[b"ALARM:1\r\n"])
    grbl = _make_backend(fake)
    with pytest.raises(AlarmError) as exc:
        grbl.send("G1 X100", blocking=False)
    assert exc.value.code == 1


def test_stop_soft_writes_feed_hold_char():
    fake = FakeSerial()
    grbl = _make_backend(fake)
    grbl.stop(soft=True)
    assert b"!" in fake.written
    assert b"\x18" not in fake.written


def test_stop_hard_writes_soft_reset_char():
    fake = FakeSerial()
    grbl = _make_backend(fake)
    grbl.stop(soft=False)
    assert b"\x18" in fake.written
