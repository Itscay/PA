"""Speech-to-text: interface + faster-whisper (BUILD_PLAN section 4/9).

* ``base.en`` int8 on CPU by default; CUDA auto-detected when present.
* Models are downloaded once with a SHA-256 manifest check (manifest lands
  with Phase 11's model manager; here we verify file presence + size).
* Input is in-RAM float32 16 kHz mono; output is text. Nothing touches disk
  beyond the model files themselves (P1).
* ``initial_prompt`` biases decoding toward app names and contacts so
  "CapCut"/"VS Code" transcribe correctly (section 8.1/12).
"""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000


@dataclass
class Transcript:
    text: str
    confidence: float = 1.0
    language: str = "en"
    latency_ms: int = 0


class SpeechToText(ABC):
    @abstractmethod
    def transcribe(self, audio: np.ndarray) -> Transcript:
        """Mono float32 16 kHz samples -> text."""


class NullSpeechToText(SpeechToText):
    """Returns queued transcripts; used by --demo and tests."""

    def __init__(self, transcripts: list[str] | None = None) -> None:
        self._queue = list(transcripts or [])
        self.calls = 0

    def transcribe(self, audio: np.ndarray) -> Transcript:
        self.calls += 1
        text = self._queue.pop(0) if self._queue else ""
        return Transcript(text=text)


@dataclass
class SttConfig:
    model: str = "base.en"
    device: str = "auto"  # auto | cpu | cuda
    compute_type: str = "int8"
    initial_prompt: str = ""
    beam_size: int = 1
    extra: dict[str, str] = field(default_factory=dict)


def detect_device() -> str:
    """'cuda' when an NVIDIA GPU is present, else 'cpu'."""
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda"
    except Exception:
        pass
    return "cpu"


class FasterWhisper(SpeechToText):
    """Local faster-whisper recogniser. Lazily loads the model on first use."""

    def __init__(self, config: SttConfig | None = None) -> None:
        self._config = config or SttConfig()
        self._model: object | None = None
        self._lock = threading.Lock()
        self.last_latency_ms = 0

    def _load(self) -> None:
        from faster_whisper import WhisperModel

        device = self._config.device
        if device == "auto":
            device = detect_device()
        compute = self._config.compute_type
        if device == "cuda" and compute == "int8":
            compute = "float16"
        log.info("loading whisper model=%s device=%s compute=%s",
                 self._config.model, device, compute)
        self._model = WhisperModel(self._config.model, device=device, compute_type=compute)

    def transcribe(self, audio: np.ndarray) -> Transcript:
        import time

        with self._lock:
            if self._model is None:
                self._load()
            assert self._model is not None
            start = time.perf_counter()
            audio = np.asarray(audio, dtype=np.float32).reshape(-1)
            segments, info = self._model.transcribe(  # type: ignore[attr-defined]
                audio,
                beam_size=self._config.beam_size,
                language="en",
                initial_prompt=self._config.initial_prompt or None,
                vad_filter=False,  # VAD/endpointing is ours (audio/vad.py)
            )
            parts = [seg.text.strip() for seg in segments]
            latency = int((time.perf_counter() - start) * 1000)
            self.last_latency_ms = latency
            text = " ".join(p for p in parts if p)
            conf = float(getattr(info, "language_probability", 1.0))
            return Transcript(text=text, confidence=conf, language="en", latency_ms=latency)
