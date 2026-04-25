"""GRBL backend over pyserial.

Implements two transmission models:
- send-response (v1, default): write line, await `ok` / `error:N` / `ALARM:N`.
- streaming (v2): character-counting streamer pushes many lines into GRBL's
  serial RX buffer (≤128 bytes) and processes acks as they arrive.

For motion commands in blocking mode, after `ok` we poll `?` until the controller
reports state=Idle and the planner buffer is full again (Bf == max).
"""

from __future__ import annotations

import logging
import re
import threading
import time
from collections import deque
from collections.abc import Iterable

from deuspy import config, gcode
from deuspy.backends.base import BackendResult, MachineStatus
from deuspy.errors import AlarmError, ConnectionLost, GrblError
from deuspy.job import Job
from deuspy.units import ORIGIN, Vec3

# GRBL 1.1 serial RX buffer is 128 bytes by default.
GRBL_RX_BUFFER = 128

log = logging.getLogger("deuspy.grbl")

_STATUS_RE = re.compile(r"<([^>]*)>")
_ALARM_RE = re.compile(r"ALARM:(\d+)")
_ERROR_RE = re.compile(r"error:(\d+)")
_NUM_RE = re.compile(r"[-+]?\d*\.?\d+")


def _parse_status(payload: str) -> MachineStatus:
    """Parse the body of a GRBL `<...>` status report."""
    parts = payload.split("|")
    state = parts[0] if parts else "Unknown"
    mpos = wpos = ORIGIN
    feed = spindle = 0.0
    bf_free = 0
    for field_str in parts[1:]:
        if ":" not in field_str:
            continue
        key, value = field_str.split(":", 1)
        if key == "MPos":
            mpos = _vec3_from(value)
        elif key == "WPos":
            wpos = _vec3_from(value)
        elif key == "Bf":
            nums = _NUM_RE.findall(value)
            if nums:
                bf_free = int(float(nums[0]))
        elif key == "FS":
            nums = _NUM_RE.findall(value)
            if len(nums) >= 1:
                feed = float(nums[0])
            if len(nums) >= 2:
                spindle = float(nums[1])
    # GRBL only sends one of MPos / WPos by default; reuse the one we got.
    if mpos is ORIGIN and wpos is not ORIGIN:
        mpos = wpos
    if wpos is ORIGIN and mpos is not ORIGIN:
        wpos = mpos
    return MachineStatus(
        state=state,
        mpos=mpos,
        wpos=wpos,
        buffer_free=bf_free,
        feed=feed,
        spindle=spindle,
    )


def _vec3_from(value: str) -> Vec3:
    coords = [float(n) for n in _NUM_RE.findall(value)]
    while len(coords) < 3:
        coords.append(0.0)
    return Vec3(coords[0], coords[1], coords[2])


def autodetect_port() -> str | None:
    """Return the first serial port that looks like a GRBL controller."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return None

    candidates = []
    for p in list_ports.comports():
        desc = f"{p.description or ''} {p.manufacturer or ''} {p.product or ''}".lower()
        if any(k in desc for k in ("arduino", "ch340", "ftdi", "wchusb", "cp210", "usb serial")):
            candidates.append(p.device)
    if not candidates:
        # Fall back to the first available port — better than nothing for the user.
        ports = [p.device for p in list_ports.comports()]
        return ports[0] if ports else None
    if len(candidates) > 1:
        log.warning("Multiple candidate ports found, picking %s of %s", candidates[0], candidates)
    return candidates[0]


class GrblBackend:
    """pyserial-based GRBL backend.

    Lifecycle:  __init__ → open() → send(...)*  → close()
    """

    name = "grbl"

    def __init__(
        self,
        *,
        port: str | None = None,
        baud: int = config.DEFAULT_BAUD,
        rw_timeout: float = config.SERIAL_RW_TIMEOUT_S,
    ) -> None:
        self._port_arg = port
        self._baud = baud
        self._rw_timeout = rw_timeout
        self._ser = None  # type: ignore[assignment]
        self._buf = b""
        self._last_status: MachineStatus | None = None
        self._max_buffer_free = 15  # GRBL default planner depth
        self._opened = False
        # Streaming state — guarded by _io_lock; only one of {send, stream} can
        # hold the port at a time.
        self._io_lock = threading.Lock()
        self._streaming = False

    def is_authoritative(self) -> bool:
        return True

    def open(self) -> None:
        try:
            import serial  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ConnectionLost(
                "pyserial is not installed; install deuspy with hardware support."
            ) from exc
        port = self._port_arg or autodetect_port()
        if port is None:
            raise ConnectionLost("No serial port specified and none could be autodetected.")
        log.info("Opening %s @ %d", port, self._baud)
        self._ser = serial.Serial(
            port=port,
            baudrate=self._baud,
            timeout=self._rw_timeout,
            write_timeout=self._rw_timeout,
        )
        self._opened = True
        # Toggle DTR to reset many GRBL boards, then drain the boot banner.
        try:
            self._ser.dtr = False
            time.sleep(0.05)
            self._ser.dtr = True
        except Exception:  # noqa: BLE001
            pass
        self._drain_for(2.0)
        # Capture initial status so we know the buffer depth.
        try:
            st = self._poll_status_once()
            if st is not None:
                self._last_status = st
                # GRBL 1.1 typically reports Bf:15 when idle.
                if st.buffer_free > self._max_buffer_free:
                    self._max_buffer_free = st.buffer_free
        except Exception as exc:  # noqa: BLE001
            log.debug("Initial status poll failed: %s", exc)

    def close(self) -> None:
        if self._ser is not None and self._opened:
            try:
                self._ser.close()
            except Exception as exc:  # noqa: BLE001
                log.warning("Serial close raised: %s", exc)
        self._opened = False
        self._ser = None

    # ------------------------------------------------------------------
    # Public protocol
    # ------------------------------------------------------------------

    def send(self, line: str, *, blocking: bool = True) -> BackendResult:
        if not self._opened or self._ser is None:
            raise ConnectionLost("GRBL backend is not open.")
        if self._streaming:
            raise ConnectionLost("Cannot send while a streaming Job is in progress.")

        payload = line.strip()
        if not payload:
            return BackendResult(ok=True)

        with self._io_lock:
            self._write(payload + "\n")
            result = self._await_ack(payload)
            if not result.ok:
                return result

            if blocking and payload.split(maxsplit=1)[0] in ("G0", "G1", "G2", "G3", "$H"):
                self._wait_idle()

        return result

    def stream(self, lines: Iterable[str], job: Job) -> None:
        """Push `lines` into GRBL using a character-counting streamer in a worker thread.

        Returns immediately after spawning the worker. The Job tracks progress;
        cancel via job.cancel() (issues feed-hold + soft-reset).
        """
        materialized = [line.strip() for line in lines if line.strip()]
        job.total_lines = len(materialized)
        thread = threading.Thread(
            target=self._stream_worker,
            args=(materialized, job),
            name="deuspy-grbl-stream",
            daemon=True,
        )
        job._thread = thread
        self._streaming = True
        thread.start()

    def _stream_worker(self, lines: list[str], job: Job) -> None:
        """Character-counting streamer. Runs on its own thread; owns _io_lock."""
        pending: deque[int] = deque()  # bytes-in-flight per outstanding line
        in_flight = 0
        idx = 0
        error: Exception | None = None

        try:
            with self._io_lock:
                while idx < len(lines) or pending:
                    if job._cancelled and pending:
                        # User asked to stop. Issue feed-hold + soft-reset and bail.
                        self._write_raw(gcode.feed_hold().encode("ascii"))
                        time.sleep(0.05)
                        self._write_raw(gcode.soft_reset().encode("ascii"))
                        self._drain_for(0.5)
                        break
                    if job._cancelled:
                        break

                    # Push as many lines as fit into GRBL's RX buffer.
                    while idx < len(lines):
                        line = lines[idx]
                        encoded_len = len(line) + 1  # newline
                        if in_flight + encoded_len > GRBL_RX_BUFFER:
                            break
                        self._write(line + "\n")
                        pending.append(encoded_len)
                        in_flight += encoded_len
                        idx += 1
                        job._mark_sent()

                    # Drain at least one response to make room for more.
                    response = self._read_line(0.5)
                    if response is None:
                        continue
                    if response == "ok":
                        if pending:
                            in_flight -= pending.popleft()
                        job._mark_acked()
                        continue
                    err = _ERROR_RE.search(response)
                    if err:
                        error = GrblError(int(err.group(1)), lines[idx - 1] if idx else "")
                        break
                    alarm = _ALARM_RE.search(response)
                    if alarm:
                        error = AlarmError(int(alarm.group(1)), response)
                        break
                    self._consume(response)
        except Exception as exc:  # noqa: BLE001
            error = exc
        finally:
            self._streaming = False
            job._finish(error)

    def status(self) -> MachineStatus:
        st = self._poll_status_once()
        if st is None:
            if self._last_status is not None:
                return self._last_status
            raise ConnectionLost("No status received from GRBL.")
        self._last_status = st
        return st

    def stop(self, *, soft: bool = True) -> None:
        if self._ser is None:
            return
        if soft:
            self._write_raw(gcode.feed_hold().encode("ascii"))
        else:
            self._write_raw(gcode.soft_reset().encode("ascii"))
            time.sleep(0.5)
            self._drain_for(1.0)

    # ------------------------------------------------------------------
    # I/O internals
    # ------------------------------------------------------------------

    def _write(self, s: str) -> None:
        log.debug(">> %s", s.rstrip())
        self._write_raw(s.encode("ascii"))

    def _write_raw(self, data: bytes) -> None:
        assert self._ser is not None
        try:
            self._ser.write(data)
            self._ser.flush()
        except Exception as exc:  # noqa: BLE001
            raise ConnectionLost(f"Serial write failed: {exc}") from exc

    def _read_line(self, timeout: float) -> str | None:
        """Read one CRLF-terminated line, or return None on timeout."""
        assert self._ser is not None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                chunk = self._ser.read(64)
            except Exception as exc:  # noqa: BLE001
                raise ConnectionLost(f"Serial read failed: {exc}") from exc
            if chunk:
                self._buf += chunk
            if b"\n" in self._buf:
                line, _, self._buf = self._buf.partition(b"\n")
                return line.decode("ascii", errors="replace").strip()
            if not chunk:
                # No data this tick; keep looping until deadline.
                continue
        return None

    def _drain_for(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            line = self._read_line(0.1)
            if line is None:
                continue
            self._consume(line)

    def _consume(self, line: str) -> None:
        """Process an asynchronous response that's not an immediate ack."""
        m = _STATUS_RE.search(line)
        if m:
            self._last_status = _parse_status(m.group(1))
            if self._last_status.buffer_free > self._max_buffer_free:
                self._max_buffer_free = self._last_status.buffer_free
            log.debug("<< %s", line)
            return
        log.debug("<< %s", line)

    def _await_ack(self, sent: str) -> BackendResult:
        """Block until GRBL acknowledges or rejects the most recently written line."""
        deadline = time.monotonic() + config.ACK_TIMEOUT_S
        while time.monotonic() < deadline:
            line = self._read_line(0.5)
            if line is None:
                continue
            if line == "ok":
                return BackendResult(ok=True, raw="ok")
            err = _ERROR_RE.search(line)
            if err:
                code = int(err.group(1))
                raise GrblError(code, sent)
            alarm = _ALARM_RE.search(line)
            if alarm:
                code = int(alarm.group(1))
                raise AlarmError(code, line)
            self._consume(line)
        raise ConnectionLost(f"Timed out waiting for ack to {sent!r}")

    def _poll_status_once(self) -> MachineStatus | None:
        if self._ser is None:
            return None
        self._write_raw(b"?")
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            line = self._read_line(0.2)
            if line is None:
                continue
            m = _STATUS_RE.search(line)
            if m:
                st = _parse_status(m.group(1))
                self._last_status = st
                return st
            self._consume(line)
        return None

    def _wait_idle(self) -> None:
        """Poll `?` until the controller reports Idle and the buffer is empty (full free)."""
        deadline = time.monotonic() + config.ACK_TIMEOUT_S * 4
        while time.monotonic() < deadline:
            st = self._poll_status_once()
            if st is None:
                time.sleep(config.POLL_INTERVAL_S)
                continue
            if st.state == "Idle" and st.buffer_free >= self._max_buffer_free:
                return
            if st.state == "Alarm":
                raise AlarmError(None, "Controller entered Alarm during motion.")
            time.sleep(config.POLL_INTERVAL_S)
        raise ConnectionLost("Timed out waiting for Idle state.")
