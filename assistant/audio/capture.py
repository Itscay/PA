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


def list_input_devices() -> list[dict[str, int | str | bool]]:
    """Enumerate host input devices for the Settings device picker."""
    import sounddevice as sd

    out: list[dict[str, int | str | bool]] = []
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


def match_device_index(
    devices: list[dict[str, int | str | bool]], spec: int | str
) -> int | None:
    """Resolve a user device spec to an index in ``devices`` (pure, testable).

    ``spec`` may be an index, ``"default"``, or a device-name fragment.

    **Names beat indices**: PortAudio/MME endpoint indices are not stable
    across runs on Windows -- measured on this machine: the raw DMIC array
    was index 21 in one process and 18 in the next, and index 21 pointed at
    a different (broken) endpoint later. A stored index can therefore select
    the *wrong microphone*, so a numeric spec is only accepted when it
    still matches, and a string spec is matched by name (case-insensitive,
    substring) with the default device as fallback.
    """
    if isinstance(spec, int):
        known = {int(d["index"]) for d in devices}
        return spec if spec in known else None
    text = str(spec).strip()
    if not text or text.lower() == "default":
        return None  # caller uses the host default
    lowered = text.lower()
    # Prefer an exact name match, then a substring match.
    for dev in devices:
        if str(dev.get("name", "")).strip().lower() == lowered:
            return int(dev["index"])
    for dev in devices:
        if lowered in str(dev.get("name", "")).lower():
            return int(dev["index"])
    return None


class Resampler:
    """Streaming mono resampler to 16 kHz (device rates vary: 44.1k/48k/16k).

    Pure and stateful only in its carry samples, so it is unit-testable:

    * integer ratios (48000 -> 16000) use box decimation (average of N
      samples), which doubles as a cheap anti-alias filter;
    * everything else (44100 -> 16000) uses linear interpolation with a
      fractional phase carry so block boundaries stay continuous.
    """

    def __init__(self, in_rate: int, out_rate: int = SAMPLE_RATE) -> None:
        if in_rate <= 0 or out_rate <= 0:
            raise ValueError("rates must be positive")
        self.in_rate = int(in_rate)
        self.out_rate = int(out_rate)
        self._passthrough = self.in_rate == self.out_rate
        self._factor = (
            self.in_rate // self.out_rate
            if self.in_rate % self.out_rate == 0
            else 0
        )
        self._carry = np.zeros(0, dtype=np.float32)
        # fractional phase in *input* samples for the interpolation path
        self._phase = 0.0

    @property
    def ratio(self) -> float:
        return self.out_rate / self.in_rate

    def process(self, samples: np.ndarray) -> np.ndarray:
        x = np.asarray(samples, dtype=np.float32).reshape(-1)
        if self._passthrough or x.size == 0:
            return x.copy()
        if self._factor:
            buf = np.concatenate([self._carry, x])
            k = (buf.size // self._factor) * self._factor
            if k == 0:
                self._carry = buf
                return np.zeros(0, dtype=np.float32)
            out = buf[:k].reshape(-1, self._factor).mean(axis=1)
            self._carry = buf[k:]
            return out.astype(np.float32)
        # linear interpolation with phase carry
        buf = np.concatenate([self._carry, x])
        step = self.in_rate / self.out_rate  # input samples per output sample
        max_idx = buf.size - 2  # every output needs buf[i] and buf[i + 1]
        if max_idx < self._phase:
            self._carry = buf
            return np.zeros(0, dtype=np.float32)
        # outputs at phase, phase+step, ... while the pair still exists
        out_len = int((max_idx - self._phase) // step) + 1
        idx = self._phase + step * np.arange(out_len, dtype=np.float64)
        idx = np.minimum(idx, float(max_idx))  # guard float rounding at the edge
        i0 = np.floor(idx).astype(np.int64)
        frac = (idx - i0).astype(np.float32)
        # i0 is int64, but numpy indexing with int64 array returns Any without stubs.
        i0_int = i0.astype(int)
        out = buf[i0_int] * (1.0 - frac) + buf[i0_int + 1] * frac
        # Keep from the last sample index consumed; the next output is the
        # one *after* idx[-1] (phase is measured from that kept sample), so
        # consecutive blocks neither duplicate nor skip a position.
        keep_from = int(i0[-1])
        self._phase = float(idx[-1] + step - keep_from)
        self._carry = buf[keep_from:]
        return out.astype(np.float32)  # type: ignore[no-any-return]


class MicCapture:
    """Owns the sounddevice input stream and feeds a RingBuffer.

    ``on_audio`` (optional) is called from the audio thread with each block.
    """

    def __init__(
        self,
        ring: RingBuffer,
        device: int | str = "default",
        sample_rate: int = SAMPLE_RATE,
        blocksize: int = 1600,  # 100 ms at ``sample_rate"
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
        # Filled in by start(): what we actually opened.
        self.opened_device: int | None = None
        self.opened_rate = 0
        self.opened_channels = 0
        self._resampler: Resampler | None = None

    @property
    def running(self) -> bool:
        return self._stream is not None

    def _callback(self, indata: np.ndarray, _frames: int, _time: object, status: object) -> None:
        if status:
            # Device went away or overflow: drop and let the watchdog restart.
            self.blocks_dropped += 1
            log.warning("audio status: %s", status)
        mono = indata.mean(axis=1) if indata.ndim > 1 else indata.reshape(-1)
        resampler = self._resampler
        if resampler is not None:
            mono = resampler.process(mono)
            if mono.size == 0:  # not enough input yet to emit a 16 kHz block
                return
        self._ring.append(mono)
        if self._on_audio is not None:
            self._on_audio(mono)

    def start(self) -> None:
        import sounddevice as sd

        with self._lock:
            if self._stream is not None:
                return
            try:
                device_index, rate, channels = self._probe(sd)
                self._resampler = (
                    None if rate == self._sample_rate else Resampler(rate, self._sample_rate)
                )
                self._stream = sd.InputStream(
                    device=device_index,
                    samplerate=rate,
                    channels=channels,
                    dtype="float32",
                    blocksize=max(1, int(round(self._blocksize * rate / self._sample_rate))),
                    callback=self._callback,
                )
                self._stream.start()
                self.opened_device = device_index
                self.opened_rate = rate
                self.opened_channels = channels
                self.last_error = None
                log.info(
                    "mic started (device=%s rate=%d ch=%d -> %d Hz)",
                    device_index,
                    rate,
                    channels,
                    self._sample_rate,
                )
            except Exception as exc:
                self._stream = None
                self.last_error = str(exc)
                log.error("mic start failed: %s", exc)
                raise

    def _probe(self, sd: Any) -> tuple[int | None, int, int]:
        """Pick the device, its native rate, and a channel count that opens.

        Two live findings drove this (Windows, Intel Smart Sound):

        * the default array device rejects ``channels=1`` (PortAudio
          ``Invalid device``) while others only expose 1 usable channel --
          so try 1 first and fall back to the device's own count (we
          downmix in the callback);
        * devices run at 44.1k/48k/16k natively, so we open at the native
          rate and resample to 16 kHz instead of forcing 16k on the device.
        """
        devices = list_input_devices()
        index = match_device_index(devices, self._device)
        info = sd.query_devices(index if index is not None else "input")
        rate = int(round(float(info["default_samplerate"])))
        max_ch = int(info["max_input_channels"])
        last_err: Exception | None = None
        for channels in (1, min(2, max_ch), max_ch):
            if channels < 1:
                continue
            try:
                sd.check_input_settings(
                    device=index, samplerate=rate, channels=channels, dtype="float32"
                )
                return index, rate, channels
            except Exception as exc:  # noqa: PERF203 - probing is inherently retry-y
                last_err = exc
        raise RuntimeError(
            f"no usable input configuration for device {self._device!r}: {last_err}"
        )

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
