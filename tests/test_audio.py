"""Audio pipeline tests (Phase 1): ring buffer, endpointer, VAD, hotkey, STT/TTS fakes."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from assistant.audio.capture import RingBuffer
from assistant.audio.hotkey import parse_hotkey
from assistant.audio.stt import NullSpeechToText, SttConfig, Transcript
from assistant.audio.tts import NullTTS
from assistant.audio.vad import (
    MODEL_SHA256,
    AudioSegmenter,
    EndpointConfig,
    Endpointer,
    SileroVad,
    VadEvent,
    ensure_model,
    verify_model,
)
from assistant.audio.wakeword import NullWakeWord

# --- RingBuffer ---------------------------------------------------------------


def test_ring_buffer_append_drain() -> None:
    rb = RingBuffer(8)
    rb.append(np.arange(5, dtype=np.float32))
    assert len(rb) == 5
    out = rb.drain()
    np.testing.assert_array_equal(out, np.arange(5, dtype=np.float32))
    assert len(rb) == 0


def test_ring_buffer_overwrites_oldest() -> None:
    rb = RingBuffer(4)
    rb.append(np.array([1, 2, 3], dtype=np.float32))
    rb.append(np.array([4, 5], dtype=np.float32))  # capacity 4 -> [3,4,5] keeps last 4
    out = rb.drain()
    assert out.shape[0] == 4
    np.testing.assert_array_equal(out, np.array([2, 3, 4, 5], dtype=np.float32))


def test_ring_buffer_wraparound() -> None:
    rb = RingBuffer(6)
    rb.append(np.array([1, 2, 3, 4], dtype=np.float32))
    rb.append(np.array([5, 6, 7], dtype=np.float32))  # 7 total, capacity 6 -> drop oldest
    out = rb.drain()
    np.testing.assert_array_equal(out, np.array([2, 3, 4, 5, 6, 7], dtype=np.float32))


def test_ring_buffer_oversized_write_keeps_tail() -> None:
    rb = RingBuffer(4)
    rb.append(np.arange(10, dtype=np.float32))
    out = rb.drain()
    np.testing.assert_array_equal(out, np.array([6, 7, 8, 9], dtype=np.float32))


def test_ring_buffer_snapshot_does_not_clear() -> None:
    rb = RingBuffer(4)
    rb.append(np.array([1, 2], dtype=np.float32))
    np.testing.assert_array_equal(rb.snapshot(), np.array([1, 2], dtype=np.float32))
    assert len(rb) == 2


def test_ring_buffer_rejects_bad_capacity() -> None:
    with pytest.raises(ValueError):
        RingBuffer(0)


# --- Endpointer (pure) --------------------------------------------------------


def test_endpointer_starts_after_min_frames() -> None:
    ep = Endpointer(EndpointConfig(min_speech_frames=3))
    assert ep.feed(0.9) == []
    assert ep.feed(0.9) == []
    assert ep.feed(0.9) == [VadEvent.SPEECH_START]
    assert ep.in_speech


def test_endpointer_starts_within_300ms_budget() -> None:
    """Start must fire in <= 300 ms of speech (Phase 1 budget)."""
    cfg = EndpointConfig()
    ep = Endpointer(cfg)
    events: list[VadEvent] = []
    for _ in range(20):
        events.extend(ep.feed(0.9))
        if events:
            break
    frames_to_start = cfg.min_speech_frames
    assert frames_to_start * cfg.frame_s <= 0.3


def test_endpointer_ends_after_1_2s_silence() -> None:
    cfg = EndpointConfig(min_speech_frames=3, silence_end_s=1.2)
    ep = Endpointer(cfg)
    for _ in range(5):
        ep.feed(0.9)
    assert ep.in_speech
    events: list[VadEvent] = []
    for _ in range(cfg.silence_frames_to_end - 1):
        events.extend(ep.feed(0.1))
        assert events == []  # not yet
    events.extend(ep.feed(0.1))
    assert events == [VadEvent.SPEECH_END]
    assert not ep.in_speech


def test_endpointer_hard_cap_8_seconds() -> None:
    cfg = EndpointConfig(min_speech_frames=3, max_utterance_s=8.0, silence_end_s=1.2)
    ep = Endpointer(cfg)
    start: list[VadEvent] = []
    for _ in range(3):
        start.extend(ep.feed(0.9))
    assert start == [VadEvent.SPEECH_START]
    events: list[VadEvent] = []
    # keep talking (never silent) well past 8 s: the cap must end the utterance
    for _ in range(cfg.max_frames + 10):
        events.extend(ep.feed(0.9))
        if events:
            break
    assert events == [VadEvent.SPEECH_END]
    assert not ep.in_speech
    assert cfg.max_utterance_s == 8.0


def test_endpointer_reset() -> None:
    ep = Endpointer(EndpointConfig(min_speech_frames=1))
    ep.feed(0.9)
    assert ep.in_speech
    ep.reset()
    assert not ep.in_speech


# --- Silero model --------------------------------------------------------------


def test_model_hash_and_download(tmp_path: Path) -> None:
    """Model download verifies SHA-256 (BUILD_PLAN section 11)."""
    path = ensure_model(tmp_path)
    assert path.exists()
    assert verify_model(path) is True
    # corrupt -> re-download
    path.write_bytes(b"garbage")
    assert verify_model(path) is False
    path2 = ensure_model(tmp_path)
    assert verify_model(path2) is True


@pytest.fixture(scope="session")
def silero_model_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Download (once per session) the Silero model into a temp models dir."""
    return ensure_model(tmp_path_factory.mktemp("models"))


@pytest.fixture(scope="session")
def spoken_audio() -> np.ndarray:
    """Session fixture: 16 kHz mono float32 speech synthesized with SAPI TTS.

    Synthetic TTS (BUILD_PLAN section 10 audio fixtures); stored in the pytest
    temp dir, never in the app data dir (P1: the app itself writes no audio).
    """
    import tempfile
    import wave

    import pyttsx3

    tmp = Path(tempfile.mkdtemp(prefix="audio_fixtures_"))
    wav = tmp / "speech.wav"
    engine = pyttsx3.init()
    engine.save_to_file("Hello there, this is a test of the voice assistant.", str(wav))
    engine.runAndWait()
    engine.stop()
    with wave.open(str(wav), "rb") as w:
        rate = w.getframerate()
        raw = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    wav.unlink(missing_ok=True)
    audio = raw.astype(np.float32) / 32768.0
    if rate != 16_000:  # SAPI emits 22.05 kHz; linear resample to 16 kHz
        n_out = int(len(audio) * 16_000 / rate)
        audio = np.interp(
            np.linspace(0, len(audio) - 1, n_out),
            np.arange(len(audio)),
            audio,
        ).astype(np.float32)
    return audio


def test_silero_prob_speech_vs_silence(
    silero_model_path: Path, spoken_audio: np.ndarray
) -> None:
    """The real ONNX model scores TTS speech higher than silence."""
    model = SileroVad(silero_model_path)
    cfg = EndpointConfig()
    win = cfg.window_samples

    def probs(chunk: np.ndarray) -> list[float]:
        return [
            float(model.prob(chunk[i : i + win]))
            for i in range(0, len(chunk) - win + 1, win)
        ]

    p_silence = probs(np.zeros(win * 10, dtype=np.float32))
    model.reset()
    p_speech = probs(spoken_audio)
    assert max(p_silence) < 0.5, p_silence
    assert max(p_speech) > 0.5, p_speech  # speech must be confidently detected
    model.reset()


def test_silero_pipeline_detects_speech_endpoints(
    silero_model_path: Path, spoken_audio: np.ndarray
) -> None:
    """samples -> windows -> probs -> SPEECH_START for real speech."""
    from assistant.audio.vad import VadPipeline

    model = SileroVad(silero_model_path)
    pipeline = VadPipeline(model, Endpointer(EndpointConfig(min_speech_frames=3)))
    events = pipeline.feed(spoken_audio)
    assert VadEvent.SPEECH_START in events


def test_silero_rejects_wrong_window_size(silero_model_path: Path) -> None:
    model = SileroVad(silero_model_path)
    with pytest.raises(ValueError):
        model.prob(np.zeros(100, dtype=np.float32))


def test_segmenter_buffers_partial_windows() -> None:
    seg = AudioSegmenter(window_samples=4)
    assert seg.feed(np.array([1, 2, 3], dtype=np.float32)) == []
    wins = seg.feed(np.array([4, 5, 6], dtype=np.float32))
    assert len(wins) == 1
    np.testing.assert_array_equal(wins[0], np.array([1, 2, 3, 4], dtype=np.float32))
    seg.flush()


def test_verify_missing_model(tmp_path: Path) -> None:
    assert verify_model(tmp_path / "nope.onnx") is False
    assert MODEL_SHA256.startswith("1a153a22")


# --- hotkey parsing ------------------------------------------------------------


def test_parse_hotkey() -> None:
    assert parse_hotkey("ctrl+alt+space") == frozenset({"ctrl", "alt", "space"})
    assert parse_hotkey("Ctrl+Shift+p") == frozenset({"ctrl", "shift", "p"})
    assert parse_hotkey("win+s") == frozenset({"cmd", "s"})
    with pytest.raises(ValueError):
        parse_hotkey("")
    with pytest.raises(ValueError):
        parse_hotkey("ctrl++space")


# --- fakes ---------------------------------------------------------------------


def test_null_stt_and_tts() -> None:
    stt = NullSpeechToText(["hello world"])
    tr = stt.transcribe(np.zeros(1600, dtype=np.float32))
    assert isinstance(tr, Transcript) and tr.text == "hello world"
    assert stt.transcribe(np.zeros(10)).text == ""
    tts = NullTTS()
    tts.speak("hi")
    assert tts.last == "hi" and tts.speaking is False
    tts.interrupt()
    assert tts.interrupts == 1


def test_null_wakeword() -> None:
    ww = NullWakeWord()
    ww.start()
    assert ww.feed(np.zeros(1280, dtype=np.float32)) == 0.0
    ww.suppress(1.0)
    assert ww.suppressed
    ww.suppress(0)
    assert not ww.suppressed
    ww.reset()
    ww.stop()


def test_stt_config_defaults() -> None:
    cfg = SttConfig()
    assert cfg.model == "base.en" and cfg.device == "auto" and cfg.compute_type == "int8"
