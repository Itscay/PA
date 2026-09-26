"""Microphone capture: sounddevice stream + ring buffer + device hot-swap (BUILD_PLAN section 9).

Rules:
* 16 kHz mono float32 internally (int16 at the wire).
* Audio lives only in RAM (P1): this module never writes to disk.
* A watchdog can restart the stream when the device disappears (unplugged or
  the default input device changed).
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

import numpy as np

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000


class RingBuffer:
    """Fixed-capacity float32 ring buffer for mono audio (RAM only, P1)."""

    def __init__(self, capacity_samples: int) -> None:
        if capacity_samples <= 0:
            raise ValueError("capacity must be positive")
        self._buf = np.zeros(capacity_samples, dtype=np.float32)
        self._capacity = capacity_samples
        self._size = 0
        self._write = 0
        self._lock = threading.Lock()

    @property
    def capacity(self) -> int:
        return self._capacity

    def __len__(self) -> int:
        with self._lock:
            return self._size

    def append(self, samples: np.ndarray) -> None:
        """Append mono samples, overwriting the oldest data if full."""
        samples = np.asarray(samples, dtype=np.float32).reshape(-1)
        n = samples.shape[0]
        if n == 0:
            return
        with self._lock:
            if n >= self._capacity:
                self._buf[:] = samples[-self._capacity:]
                self._write = 0
                self._size = self._capacity
                return
            end = self._write + n
            if end <= self._capacity:
                self._buf[self._write:end] = samples
            else:
                first = self._capacity - self._write
                self._buf[self._write:] = samples[:first]
                self._buf[: end - self._capacity] = samples[first:]
            self._write = end % self._capacity
            self._size = min(self._size + n, self._capacity)

    def drain(self) -> np.ndarray:
        """Return all buffered samples and clear the buffer."""
        with self._lock:
            if self._size == 0:
                return np.zeros(0, dtype=np.float32)
            if self._size < self._capacity:
                out = self._buf[: self._size].copy()
            else:
                out = np.roll(self._buf, -self._write).copy()
            self._size = 0
            self._write = 0
            return out

    def snapshot(self) -> np.ndarray:
        """Return a copy of the buffered samples without clearing."""
        with self._lock:
            return self.drain_locked_copy()

    def drain_locked_copy(self) -> np.ndarray:
        if self._size == 0:
            return np.zeros(0, dtype=np.float32)
        if self._size < self._capacity:
            return self._buf[: self._size].copy()
        return np.roll(self._buf, -self._write).copy()


def list_input_devices() -> list[dict[str, object]]:
    """Enumerate host input devices for the Settings device picker."""
    import sounddevice as sd

    out: list[dict[str, object]] = []
    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            out.append(
                {
                    "index": i,
                    "name": str(dev["name"]),
                    "channels": int(dev["max_input_channels"]),
                    "default": i == sd.default.device[0],
                }
            )
    return out


def default_input_device() -> int | str:
    import sounddevice as sd

    dev = sd.default.device[0]
    return "default" if dev is None else int(dev)


class MicCapture:
    """Owns the sounddevice input stream and feeds a RingBuffer.

    ``on_audio`` (optional) is called from the audio thread with each block.
    """

    def __init__(
        self,
        ring: RingBuffer,
        device: int | str = "default",
        sample_rate: int = SAMPLE_RATE,
        blocksize: int = 1600,  # 100 ms
        on_audio: Callable[[np.ndarray], None] | None = None,
    ) -> None:
        self._ring = ring
        self._device = device
        self._sample_rate = sample_rate
        self._blocksize = blocksize
        self._on_audio = on_audio
        # sounddevice ships no stubs; stream is guarded by self._lock.
        self._stream: Any = None
        self._lock = threading.Lock()
        self.blocks_dropped = 0
        self.last_error: str | None = None

    @property
    def running(self) -> bool:
        return self._stream is not None

    def _callback(self, indata: np.ndarray, _frames: int, _time: object, status: object) -> None:
        if status:
            # Device went away or overflow: drop and let the watchdog restart.
            self.blocks_dropped += 1
            log.warning("audio status: %s", status)
        mono = indata.mean(axis=1) if indata.ndim > 1 else indata.reshape(-1)
        self._ring.append(mono)
        if self._on_audio is not None:
            self._on_audio(mono)

    def start(self) -> None:
        import sounddevice as sd

        with self._lock:
            if self._stream is not None:
                return
            try:
                self._stream = sd.InputStream(
                    device=None if self._device == "default" else self._device,
                    samplerate=self._sample_rate,
                    channels=1,
                    dtype="float32",
                    blocksize=self._blocksize,
                    callback=self._callback,
                )
                self._stream.start()
                self.last_error = None
                log.info("mic started (device=%s)", self._device)
            except Exception as exc:
                self._stream = None
                self.last_error = str(exc)
                log.error("mic start failed: %s", exc)
                raise

    def stop(self) -> None:
        with self._lock:
            stream = self._stream
            self._stream = None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                log.exception("mic stop failed")

    def restart(self) -> None:
        self.stop()
        self.start()


class DeviceWatch:
    """Polls the default input device; fires ``on_change`` when it changes."""

    def __init__(
        self,
        on_change: Callable[[], None],
        interval_s: float = 5.0,
        get_default: Callable[[], object] | None = None,
    ) -> None:
        self._on_change = on_change
        self._interval = interval_s
        self._get_default = get_default or default_input_device
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last: object | None = None

    def start(self) -> None:
        try:
            self._last = self._get_default()
        except Exception:
            self._last = None
        self._thread = threading.Thread(target=self._run, name="device-watch", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                current = self._get_default()
            except Exception:
                continue
            if current != self._last:
                log.info("input device changed: %s -> %s", self._last, current)
                self._last = current
                try:
                    self._on_change()
                except Exception:
                    log.exception("device change handler failed")

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self._interval + 1)
            self._thread = None


def wait_for_device(timeout_s: float = 10.0) -> bool:
    """Watchdog helper: wait until an input device exists again."""
    import sounddevice as sd

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if any(d["max_input_channels"] > 0 for d in sd.query_devices()):
                return True
        except Exception:
            pass
        time.sleep(1.0)
    return False
