"""Voice activity detection and utterance endpointing (BUILD_PLAN section 9).

Two layers, deliberately separated:

* :class:`SileroVad` -- thin ONNX wrapper around the Silero VAD model
  (``models/silero_vad.onnx``, SHA-256 checked). Frame level: 256 samples
  @ 16 kHz -> speech probability.
* :class:`Endpointer` -- **pure** endpointing decisions on those probabilities
  (start fast, end after 1.2 s of silence, hard cap at 8 s). No I/O, fully
  unit-testable with synthetic probability streams.

Audio stays in RAM only (P1); nothing here writes to disk except the model
download itself (which is a model, not audio).
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
# The pinned Silero model (see MODEL_SHA256) scores correctly with 16 ms
# windows @ 16 kHz; verified empirically against SAPI-synthesized speech
# (256 -> max prob 0.97, 512 -> 0.007). See tests/test_audio.py.
WINDOW_SAMPLES = 256

MODEL_URL = (
    "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
)
MODEL_SHA256 = "1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3"


class VadEvent(StrEnum):
    SPEECH_START = "speech_start"
    SPEECH_END = "speech_end"


@dataclass
class EndpointConfig:
    threshold: float = 0.5
    min_speech_frames: int = 3  # ~96 ms: keeps start well under the 300 ms budget
    silence_end_s: float = 1.2
    max_utterance_s: float = 8.0
    window_samples: int = WINDOW_SAMPLES
    sample_rate: int = SAMPLE_RATE

    @property
    def frame_s(self) -> float:
        return self.window_samples / self.sample_rate

    @property
    def silence_frames_to_end(self) -> int:
        return max(1, round(self.silence_end_s / self.frame_s))

    @property
    def max_frames(self) -> int:
        return max(1, round(self.max_utterance_s / self.frame_s))


@dataclass
class Endpointer:
    """Pure speech start/end decisions from per-frame speech probabilities."""

    config: EndpointConfig = field(default_factory=EndpointConfig)
    in_speech: bool = False
    _speech_run: int = 0
    _silence_run: int = 0
    _speech_frames: int = 0

    def reset(self) -> None:
        self.in_speech = False
        self._speech_run = 0
        self._silence_run = 0
        self._speech_frames = 0

    def feed(self, prob: float) -> list[VadEvent]:
        """Feed one frame probability; returns events it triggers."""
        cfg = self.config
        events: list[VadEvent] = []
        is_speech = prob >= cfg.threshold

        if not self.in_speech:
            self._speech_run = self._speech_run + 1 if is_speech else 0
            self._silence_run = 0
            if self._speech_run >= cfg.min_speech_frames:
                self.in_speech = True
                self._speech_frames = self._speech_run
                self._silence_run = 0
                events.append(VadEvent.SPEECH_START)
        else:
            self._speech_frames += 1
            if is_speech:
                self._silence_run = 0
            else:
                self._silence_run += 1
            if self._silence_run >= cfg.silence_frames_to_end:
                events.append(VadEvent.SPEECH_END)
                self.in_speech = False
                self._speech_run = 0
                self._silence_run = 0
                self._speech_frames = 0
            elif self._speech_frames >= cfg.max_frames:
                events.append(VadEvent.SPEECH_END)
                self.in_speech = False
                self._speech_run = 0
                self._silence_run = 0
                self._speech_frames = 0
        return events


def verify_model(path: Path) -> bool:
    """SHA-256 check per BUILD_PLAN section 11 model manifest."""
    import hashlib

    if not path.exists():
        return False
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest == MODEL_SHA256


def ensure_model(models_dir: Path) -> Path:
    """Download the Silero model if missing/corrupt. Returns the model path."""
    import hashlib
    import urllib.request

    models_dir.mkdir(parents=True, exist_ok=True)
    dest = models_dir / "silero_vad.onnx"
    if verify_model(dest):
        return dest
    log.info("downloading Silero VAD model to %s", dest)
    tmp = dest.with_suffix(".tmp")
    urllib.request.urlretrieve(MODEL_URL, tmp)  # noqa: S310 - pinned HTTPS URL
    digest = hashlib.sha256(tmp.read_bytes()).hexdigest()
    if digest != MODEL_SHA256:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"Silero VAD model SHA-256 mismatch: got {digest}, expected {MODEL_SHA256}"
        )
    tmp.replace(dest)
    return dest


class SileroVad:
    """ONNX Silero VAD: frame (256 samples) -> speech probability."""""

    def __init__(self, model_path: Path) -> None:
        import onnxruntime as ort

        self._session = ort.InferenceSession(
            str(model_path), providers=["CPUExecutionProvider"]
        )
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._state = np.zeros((2, 1, 128), dtype=np.float32)

    def prob(self, window: np.ndarray) -> float:
        """Speech probability for one 256-sample window (mono float32)."""
        window = np.asarray(window, dtype=np.float32).reshape(-1)
        if window.shape[0] != WINDOW_SAMPLES:
            raise ValueError(f"expected {WINDOW_SAMPLES} samples, got {window.shape[0]}")
        with self._lock:
            out, self._state = self._session.run(
                ["output", "stateN"],
                {
                    "input": window.reshape(1, -1),
                    "state": self._state,
                    "sr": np.array(SAMPLE_RATE, dtype=np.int64),
                },
            )
        return float(out[0][0])


class AudioSegmenter:
    """Accumulates mono samples and yields fixed windows for the VAD."""

    def __init__(self, window_samples: int = WINDOW_SAMPLES) -> None:
        self._window = window_samples
        self._pending = np.zeros(0, dtype=np.float32)

    def feed(self, samples: np.ndarray) -> list[np.ndarray]:
        samples = np.asarray(samples, dtype=np.float32).reshape(-1)
        self._pending = np.concatenate([self._pending, samples]) if self._pending.size else samples
        windows: list[np.ndarray] = []
        while self._pending.shape[0] >= self._window:
            windows.append(self._pending[: self._window])
            self._pending = self._pending[self._window:]
        return windows

    def flush(self) -> None:
        self._pending = np.zeros(0, dtype=np.float32)


class VadPipeline:
    """samples -> windows -> probabilities -> endpointer events.

    Wire this to the mic callback; it is the bridge between :class:`SileroVad`
    (model) and :class:`Endpointer` (decisions).
    """

    def __init__(
        self,
        model: SileroVad,
        endpointer: Endpointer | None = None,
        on_event: Callable[[VadEvent], None] | None = None,
    ) -> None:
        self._model = model
        self._ender = endpointer or Endpointer()
        self._segmenter = AudioSegmenter(self._ender.config.window_samples)
        self._on_event = on_event
        self.events_fired: list[VadEvent] = []

    @property
    def endpointer(self) -> Endpointer:
        return self._ender

    def feed(self, samples: np.ndarray) -> list[VadEvent]:
        events: list[VadEvent] = []
        for window in self._segmenter.feed(samples):
            prob = self._model.prob(window)
            for ev in self._ender.feed(prob):
                events.append(ev)
                self.events_fired.append(ev)
                if self._on_event is not None:
                    self._on_event(ev)
        return events

    def reset(self) -> None:
        self._model.reset()
        self._ender.reset()
        self._segmenter.flush()


def synthesize_tone(
    seconds: float, freq: float = 440.0, amplitude: float = 0.5
) -> np.ndarray:
    """Test helper: mono sine tone at 16 kHz (never used by the app)."""
    n = int(seconds * SAMPLE_RATE)
    t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def probabilities_from(
    model: SileroVad, chunks: Iterable[np.ndarray]
) -> list[float]:
    """Run an iterable of 512-sample windows through the model."""
    return [model.prob(c) for c in chunks]
