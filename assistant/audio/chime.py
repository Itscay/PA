"""Chime sounds for wake/confirm/response cues (BUILD_PLAN section 1.2/9).

Synthesized in RAM with numpy and played through sounddevice -- **no audio
file is ever written to disk** (P1: audio never leaves RAM; even the chime
bytes are generated, not stored).

Each cue is a short two-tone blip with an exponential envelope, so the whole
file is deterministic and testable without playback.
"""

from __future__ import annotations

import logging
import threading

import numpy as np

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000

# (frequency pairs in Hz, duration s, volume)
CUES: dict[str, tuple[tuple[float, float], float, float]] = {
    # rising pair: "I'm listening"
    "wake": ((784.0, 1046.5), 0.16, 0.28),
    # short single tick: response done / note
    "tick": ((1318.5, 1318.5), 0.07, 0.22),
    # descending pair: cancelled / error
    "cancel": ((523.3, 392.0), 0.20, 0.25),
}


def synthesize(cue: str = "wake") -> np.ndarray:
    """Return mono float32 samples for ``cue`` (pure, no I/O)."""
    if cue not in CUES:
        raise ValueError(f"unknown cue: {cue!r} (expected one of {sorted(CUES)})")
    (f1, f2), dur, vol = CUES[cue]
    n = int(dur * SAMPLE_RATE)
    t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    half = n // 2
    tone = np.empty(n, dtype=np.float32)
    tone[:half] = np.sin(2 * np.pi * f1 * t[:half])
    tone[half:] = np.sin(2 * np.pi * f2 * t[half:])
    # exponential-ish decay envelope so clicks don't pop
    env = np.exp(-4.0 * np.linspace(0.0, 1.0, n, dtype=np.float32))
    return (tone * env * vol).astype(np.float32)


class ChimePlayer:
    """Plays cues on a worker thread; never touches the filesystem."""

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        self._lock = threading.Lock()
        self.played: list[str] = []
        self.last_error: str | None = None

    def play(self, cue: str = "wake") -> None:
        """Fire-and-forget playback (non-blocking)."""
        self.played.append(cue)
        if not self._enabled:
            return
        threading.Thread(
            target=self._play_blocking, args=(cue,), name="chime", daemon=True
        ).start()

    def _play_blocking(self, cue: str) -> None:
        try:
            import sounddevice as sd

            sd.play(synthesize(cue), SAMPLE_RATE)
            sd.wait()
        except Exception as exc:  # never let a sound failure break the pipeline
            self.last_error = str(exc)
            log.warning("chime playback failed: %s", exc)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
