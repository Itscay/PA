"""Wake word engines (BUILD_PLAN section 4/9).

Interface + openWakeWord implementation (pre-trained "hey jarvis" model for
v1). Porcupine and custom models are Phase 12 behind the same interface.

The engine only ever sees in-RAM audio; it never writes files (P1). While TTS
is speaking the orchestrator calls :meth:`WakeWordEngine.suppress` so the
assistant doesn't wake itself (with a short tail after speech ends).
"""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import numpy as np

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
_WINDOW = 1280  # openWakeWord consumes 80 ms frames @ 16 kHz
# Score in 160 ms batches: onnxruntime session.run() has ~1 ms fixed overhead
# per call, so halving call rate roughly halves idle CPU (measured 3.6% -> ~2%
# of one core) while adding <=160 ms to detection latency -- still inside the
# <300 ms wake->overlay budget (BUILD_PLAN 3.4). openWakeWord explicitly
# supports any multiple of 80 ms.
_FEED_BATCH = 2560


def _fast_streaming_melspectrogram(self: Any, n_samples: int) -> None:
    """O(tail) replacement for openWakeWord's ``_streaming_melspectrogram``.

    Stock code does ``list(self.raw_data_buffer)[-n_samples-480:]`` every
    80 ms frame: it converts the whole 10-second deque (~153k Python ints,
    ~1.5 ms measured on this machine) just to read the last ~1760 samples.
    That was 44% of per-frame CPU, pushing idle wake-word cost from ~2.5% to
    ~4.3% of one core (budget: <3%, BUILD_PLAN 3.4).

    The deque is only ever *read* for its tail (verified by grep over
    openwakeword 0.6.x: init/clear/len-check/extend + this tail read), so
    reading the tail in O(tail) via ``reversed()`` is behaviour-identical.
    :func:`_ensure_fast_preprocessor` installs this only when the stock
    method still contains the pattern it patches.
    """
    from itertools import islice

    buf = self.raw_data_buffer
    if len(buf) < 400:
        raise ValueError(
            "The number of input frames must be at least 400 samples @ 16khz (25 ms)!"
        )
    need = n_samples + 160 * 3
    tail = list(islice(reversed(buf), 0, need))
    tail.reverse()
    self.melspectrogram_buffer = np.vstack(
        (self.melspectrogram_buffer, self._get_melspectrogram(tail))
    )
    if self.melspectrogram_buffer.shape[0] > self.melspectrogram_max_len:
        self.melspectrogram_buffer = self.melspectrogram_buffer[
            -self.melspectrogram_max_len:, :
        ]


def _ensure_fast_preprocessor() -> bool:
    """Install :func:`_fast_streaming_melspectrogram` if it is still valid.

    Returns True when the fast path is active (installed now or earlier).
    Never raises: on any doubt we keep openWakeWord's stock behaviour.
    """
    import inspect

    try:
        from openwakeword.utils import AudioFeatures

        current = getattr(AudioFeatures, "_fast_preprocessor", False)
        if current:
            return True
        stock_src = inspect.getsource(AudioFeatures._streaming_melspectrogram)
        if "list(self.raw_data_buffer)" not in stock_src:
            log.warning(
                "openWakeWord _streaming_melspectrogram changed; "
                "keeping stock (slower) preprocessor"
            )
            return False
        AudioFeatures._streaming_melspectrogram = _fast_streaming_melspectrogram
        AudioFeatures._fast_preprocessor = True
        log.info("installed O(tail) wake-word preprocessor optimization")
        return True
    except Exception:
        log.exception("could not install fast preprocessor; using stock")
        return False


class WakeWordEngine(ABC):
    """Common interface for wake word backends."""

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def feed(self, samples: np.ndarray) -> float:
        """Feed mono float32 16 kHz samples; returns wake probability 0..1."""

    @abstractmethod
    def reset(self) -> None:
        """Clear internal state (e.g. after TTS suppresses detection)."""

    @property
    @abstractmethod
    def suppressed(self) -> bool: ...

    @abstractmethod
    def suppress(self, seconds: float) -> None:
        """Ignore detections for ``seconds`` (used while TTS is speaking)."""


class NullWakeWord(WakeWordEngine):
    """Does nothing; used in --demo and tests."""

    def __init__(self) -> None:
        self._suppressed = False

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def feed(self, samples: np.ndarray) -> float:
        return 0.0

    def reset(self) -> None:
        pass

    @property
    def suppressed(self) -> bool:
        return self._suppressed

    def suppress(self, seconds: float) -> None:
        self._suppressed = seconds > 0


class OpenWakeWord(WakeWordEngine):
    """openWakeWord with the pre-trained "hey_jarvis" model."""

    def __init__(
        self,
        model_name: str = "hey_jarvis",
        sensitivity: float = 0.5,
        models_dir: Path | None = None,
    ) -> None:
        if not 0.0 <= sensitivity <= 1.0:
            raise ValueError("sensitivity must be 0..1")
        self._model_name = model_name
        self._sensitivity = sensitivity
        self._models_dir = models_dir
        self._model: object | None = None
        self._pending = np.zeros(0, dtype=np.float32)
        self._suppressed = False
        self._suppress_until = 0.0
        self._lock = threading.Lock()
        self.last_score = 0.0

    def start(self) -> None:
        import openwakeword.utils

        # Idle-CPU optimization, safe fallback (see _fast_streaming_melspectrogram).
        _ensure_fast_preprocessor()
        # Downloads model files on first ever use; no-op when cached.
        openwakeword.utils.download_models([self._model_name])
        from openwakeword import Model

        kwargs: dict[str, object] = {"wakeword_models": [self._model_name]}
        if self._models_dir is not None:
            kwargs["model_path"] = [str(self._models_dir / f"{self._model_name}.onnx")]
        self._model = Model(**kwargs)
        log.info("wake word model loaded: %s", self._model_name)

    def stop(self) -> None:
        self._model = None

    def feed(self, samples: np.ndarray) -> float:
        """Feed mono float32 16 kHz samples; returns wake probability 0..1.

        openWakeWord scores **int16** input: float32 in [-1, 1] yields ~0.0001
        on real speech while int16 yields 0.99 (verified empirically on
        Windows). The mic pipeline stays float32, so we convert here.
        """
        samples = np.asarray(samples, dtype=np.float32).reshape(-1)
        with self._lock:
            self._pending = (
                np.concatenate([self._pending, samples]) if self._pending.size else samples
            )
            score = 0.0
            while self._model is not None and self._pending.shape[0] >= _FEED_BATCH:
                frame = self._pending[:_FEED_BATCH]
                self._pending = self._pending[_FEED_BATCH:]
                frame_i16 = np.clip(frame * 32767.0, -32768, 32767).astype(np.int16)
                result = self._model.predict(frame_i16)  # type: ignore[attr-defined]
                # result: {model_name: score}
                score = max(float(v) for v in result.values()) if result else 0.0
                self.last_score = score
            if self._suppressed:
                return 0.0
            return score

    def reset(self) -> None:
        with self._lock:
            self._pending = np.zeros(0, dtype=np.float32)
            if self._model is not None:
                self._model.reset()  # type: ignore[attr-defined]

    @property
    def suppressed(self) -> bool:
        return self._suppressed

    def suppress(self, seconds: float) -> None:
        import time

        if seconds <= 0:
            self._suppressed = False
            return
        self._suppressed = True
        self._suppress_until = time.monotonic() + seconds
        # Auto-unsuppress on a timer thread (short, daemon).
        def _release() -> None:
            time.sleep(seconds)
            self._suppressed = False

        threading.Thread(target=_release, daemon=True, name="wake-suppress").start()

    def wake_threshold(self) -> float:
        return self._sensitivity
