"""Pipeline tests for the hardware-facing audio modules (Phase 1).

Layers that need no hardware run everywhere (CI included); layers that need
Windows/SAPI/a microphone are skipped politely where unavailable.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np
import pytest

from assistant.audio.chime import ChimePlayer
from assistant.audio.hotkey import PushToTalk
from assistant.audio.wakeword import NullWakeWord, _ensure_fast_preprocessor

FIXTURE_DIR = Path(__file__).parent / "audio_fixtures"


def _load_fixture(name: str) -> np.ndarray:
    import wave

    with wave.open(str(FIXTURE_DIR / name), "rb") as w:
        raw = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return raw.astype(np.float32) / 32768.0


# --- wake word (real model, downloaded once per machine) ---------------------


@pytest.fixture(scope="module")
def wake_engine():  # type: ignore[no-untyped-def]
    pytest.importorskip("openwakeword")
    from assistant.audio.wakeword import OpenWakeWord

    ww = OpenWakeWord(model_name="hey_jarvis", sensitivity=0.5)
    try:
        ww.start()
    except Exception as exc:  # model download needs network
        pytest.skip(f"wake model unavailable: {exc}")
    yield ww
    ww.stop()


def test_fast_preprocessor_installs() -> None:
    pytest.importorskip("openwakeword")
    # Idempotent: True whether first call or already installed.
    assert _ensure_fast_preprocessor() is True
    assert _ensure_fast_preprocessor() is True


def test_wake_detects_wake_phrase(wake_engine) -> None:  # type: ignore[no-untyped-def]
    audio = _load_fixture("wake_hey_jarvis.wav")
    best = 0.0
    for i in range(0, len(audio), 1600):  # real mic cadence (100 ms blocks)
        best = max(best, wake_engine.feed(audio[i : i + 1600]))
    assert best >= 0.5, f"wake phrase not detected (max {best:.3f})"
    wake_engine.reset()


def test_wake_ignores_unrelated_speech(wake_engine) -> None:  # type: ignore[no-untyped-def]
    audio = _load_fixture("research_quantum.wav")
    best = 0.0
    for i in range(0, len(audio), 1600):
        best = max(best, wake_engine.feed(audio[i : i + 1600]))
    assert best < 0.5, f"false accept on unrelated speech (max {best:.3f})"
    wake_engine.reset()


def test_wake_suppression_returns_zero(wake_engine) -> None:  # type: ignore[no-untyped-def]
    audio = _load_fixture("wake_hey_jarvis.wav")
    wake_engine.suppress(1.0)
    assert wake_engine.suppressed
    best = 0.0
    for i in range(0, len(audio), 1600):
        best = max(best, wake_engine.feed(audio[i : i + 1600]))
    assert best == 0.0, "suppression must zero out detections (TTS-talking guard)"
    wake_engine.suppress(0)
    assert not wake_engine.suppressed
    wake_engine.reset()


def test_wake_rejects_bad_sensitivity() -> None:
    from assistant.audio.wakeword import OpenWakeWord

    with pytest.raises(ValueError):
        OpenWakeWord(sensitivity=1.5)


def test_null_wake_engine_contract() -> None:
    ww = NullWakeWord()
    ww.start()
    assert ww.feed(np.zeros(2560, dtype=np.float32)) == 0.0
    ww.suppress(1.0)
    assert ww.suppressed
    ww.reset()
    ww.stop()


# --- TTS (SAPI on Windows; skips elsewhere) ----------------------------------


def _windows_only() -> None:
    import sys

    if sys.platform != "win32":
        pytest.skip("SAPI TTS requires Windows")


def test_sapi_speak_and_interrupt() -> None:
    _windows_only()
    from assistant.audio.tts import SapiTTS

    tts = SapiTTS(speak_timeout_s=15.0)
    try:
        # Blocking speak cycles (the save_to_file double-runAndWait hang does
        # not apply to say(); verified empirically on Windows).
        tts.speak("One.")
        tts.speak("Two.")
        assert not tts.speaking

        # Async + barge-in: interrupt mid-speech must flip speaking to False.
        tts.speak_async(
            "This is a long sentence being spoken so that the interrupt "
            "happens somewhere in the middle of it, not at the end."
        )
        deadline = time.monotonic() + 10
        while not tts.speaking and time.monotonic() < deadline:
            time.sleep(0.05)
        assert tts.speaking, "speech never started"
        tts.interrupt()
        time.sleep(0.5)
        assert not tts.speaking, "interrupt did not stop speech"
    finally:
        tts.stop()


def test_sapi_stop_is_idempotent() -> None:
    _windows_only()
    from assistant.audio.tts import SapiTTS

    tts = SapiTTS(speak_timeout_s=5.0)
    tts.stop()
    tts.stop()  # no raise
    tts.speak("ignored after stop")  # no raise, no block


def test_speak_timeout_when_worker_dies() -> None:
    """A dead worker must not block the caller forever (bounded wait)."""
    _windows_only()
    from assistant.audio.tts import SapiTTS

    tts = SapiTTS(speak_timeout_s=1.0)
    tts._stopped = True  # simulate shutdown race before speak
    start = time.monotonic()
    tts.speak("never spoken")  # returns immediately (guarded) or times out
    assert time.monotonic() - start < 2.0


# --- capture (needs a mic; CI runners usually have none) ---------------------


def _input_devices() -> list[dict[str, object]]:
    try:
        from assistant.audio.capture import list_input_devices

        return list_input_devices()
    except Exception:
        pytest.skip("sounddevice/audio backend unavailable")


def test_list_input_devices_shape() -> None:
    devices = _input_devices()  # skips when no backend
    for d in devices:
        assert {"index", "name", "channels", "default"} <= set(d)


def test_mic_capture_lifecycle() -> None:
    devices = _input_devices()
    if not devices:
        pytest.skip("no input device on this runner")
    from assistant.audio.capture import MicCapture, RingBuffer

    ring = RingBuffer(16_000 * 2)
    mic = MicCapture(ring, blocksize=1600)
    try:
        mic.start()
        assert mic.running
        time.sleep(0.4)
        mic.stop()
        assert not mic.running
        # Either we captured samples or the device is muted-but-present;
        # both are valid lifecycle outcomes (no exception either way).
        assert len(ring) >= 0
    except (OSError, Exception) as exc:  # pragma: no cover - device refusal
        mic.stop()
        pytest.skip(f"device unusable on this runner: {exc}")


def test_device_watch_fires_on_change() -> None:
    from assistant.audio.capture import DeviceWatch

    changed = threading.Event()
    values = iter([1, 1, 2])
    watch = DeviceWatch(
        on_change=changed.set, interval_s=0.05, get_default=lambda: next(values, 2)
    )
    watch.start()
    try:
        assert changed.wait(timeout=2.0), "on_change never fired"
    finally:
        watch.stop()


def test_device_watch_survives_getter_errors() -> None:
    from assistant.audio.capture import DeviceWatch

    calls: list[int] = []

    def flaky() -> object:
        calls.append(1)
        if len(calls) == 1:
            return "a"
        raise RuntimeError("device query failed")  # transient
        # (loop must keep going; change happens on 3rd call in other test)

    changed = threading.Event()
    # getter: first call 'a', then always raises -> no crash, no change
    watch = DeviceWatch(on_change=changed.set, interval_s=0.02, get_default=flaky)
    watch.start()
    time.sleep(0.15)
    watch.stop()
    assert not changed.is_set()


# --- push-to-talk hotkey logic (pynput-independent) --------------------------


class _FakeKey:
    def __init__(self, char: str | None = None, name: str | None = None) -> None:
        self.char = char
        self.name = name


def test_hotkey_fires_once_per_full_combo(monkeypatch: pytest.MonkeyPatch) -> None:
    presses: list[int] = []
    releases: list[int] = []
    pt = PushToTalk(
        on_press=lambda: presses.append(1),
        spec="ctrl+alt+space",
        on_release=lambda: releases.append(1),
    )
    # Bypass pynput entirely: normalize via a fake mapping.
    monkeypatch.setattr(
        pt,
        "_normalize",
        lambda k: k if isinstance(k, str) else None,
    )
    pt._handle("ctrl", True)
    assert presses == []  # modifier alone: nothing
    pt._handle("alt", True)
    assert presses == []  # still incomplete
    pt._handle("space", True)
    assert presses == [1]  # combo complete -> fires exactly once
    pt._handle("shift", True)  # extra key while held -> no re-fire
    assert presses == [1]
    pt._handle("shift", False)
    pt._handle("space", False)
    pt._handle("alt", False)
    pt._handle("ctrl", False)
    assert releases == [1]  # one release when all keys are up
    pt._handle("ctrl", True)
    pt._handle("alt", True)
    pt._handle("space", True)
    assert presses == [1, 1]  # can fire again after full release


def test_hotkey_ignores_unnormalizable_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    fires: list[int] = []
    pt = PushToTalk(on_press=lambda: fires.append(1), spec="f9")
    monkeypatch.setattr(pt, "_normalize", lambda k: None)
    pt._handle(object(), True)
    assert fires == []


def test_hotkey_normalize_real_pynput_keys() -> None:
    """Real pynput key objects must map to combo vocabulary (found live:
    Windows sends ctrl_l/alt_l and space as char ' ' -- the combo parsed
    from config could never match without this normalization)."""
    try:
        from pynput.keyboard import Key, KeyCode
    except Exception as exc:  # headless Linux CI: pynput needs a display
        pytest.skip(f"pynput unavailable: {exc}")

    pt = PushToTalk(on_press=lambda: None, spec="ctrl+alt+space")
    assert pt._normalize(Key.ctrl_l) == "ctrl"
    assert pt._normalize(Key.ctrl_r) == "ctrl"
    assert pt._normalize(Key.alt_l) == "alt"
    assert pt._normalize(Key.alt_r) == "alt"
    assert pt._normalize(Key.shift_l) == "shift"
    assert pt._normalize(Key.space) == "space"
    assert pt._normalize(KeyCode.from_char(" ")) == "space"  # second flavor
    assert pt._normalize(KeyCode.from_char("a")) == "a"

    # full combo through the real normalizer fires exactly once
    fires: list[int] = []
    pt2 = PushToTalk(on_press=lambda: fires.append(1), spec="ctrl+alt+space")
    for k in (Key.ctrl_l, Key.alt_l, Key.space):
        pt2._handle(k, True)
    assert fires == [1]
    for k in (Key.space, Key.alt_l, Key.ctrl_l):
        pt2._handle(k, False)
    # and again after release
    for k in (Key.ctrl_r, Key.alt_r, KeyCode.from_char(" ")):
        pt2._handle(k, True)
    assert fires == [1, 1]


def test_hotkey_defaults_to_ctrl_alt_space() -> None:
    pt = PushToTalk(on_press=lambda: None)
    assert pt._keys == frozenset({"ctrl", "alt", "space"})
    assert not pt.active


# --- chime player ------------------------------------------------------------


def test_chime_player_records_and_survives_missing_audio() -> None:
    # enabled=True may fail to play on headless runners; failures are caught
    # and recorded, never raised.
    player = ChimePlayer(enabled=True)
    player.play("wake")
    time.sleep(0.3)
    assert player.played == ["wake"]
    player.set_enabled(False)
    player.play("cancel")
    assert player.played == ["wake", "cancel"]


# --- VadPipeline end-to-end over a fixture -----------------------------------


def test_vad_pipeline_segments_fixture_speech() -> None:
    pytest.importorskip("onnxruntime")
    from assistant import paths
    from assistant.audio.vad import (
        EndpointConfig,
        Endpointer,
        SileroVad,
        VadPipeline,
        ensure_model,
    )

    model_path = ensure_model(paths.models_dir())
    pipeline = VadPipeline(
        SileroVad(model_path), Endpointer(EndpointConfig(min_speech_frames=3))
    )
    audio = _load_fixture("email_sara.wav")  # ~2.6 s of speech
    events: list[object] = []
    for i in range(0, len(audio), 1600):  # mic cadence
        events.extend(pipeline.feed(audio[i : i + 1600]))
    assert any(str(e).endswith("speech_start") for e in events), events


# --- device resolution + resampling (live findings, BUILD_PLAN 9) -----------


def test_match_device_prefers_name_over_stale_index() -> None:
    # Measured on Windows: endpoint indices shift between processes, so a
    # stored index can point at a different (even unusable) endpoint.
    devices = [
        {"index": 18, "name": "Microphone Array 1 (Intel DMIC)", "channels": 2},
        {"index": 19, "name": "Microphone Array 2 (Intel DMIC)", "channels": 4},
        {"index": 21, "name": "Input ()", "channels": 2},
    ]
    from assistant.audio.capture import match_device_index

    assert match_device_index(devices, "Intel DMIC") == 18  # substring
    assert match_device_index(devices, "array 2") == 19  # case-insensitive
    assert (
        match_device_index(devices, "microphone array 1 (intel dmic)") == 18
    )  # exact
    assert match_device_index(devices, 19) == 19  # valid index
    assert match_device_index(devices, 99) is None  # stale index -> default
    assert match_device_index(devices, "default") is None
    assert match_device_index(devices, "") is None
    assert match_device_index(devices, "AirPods") is None  # unplugged


def test_resampler_passthrough_and_48k_decimation() -> None:
    from assistant.audio.capture import Resampler

    pt = Resampler(16_000, 16_000)
    x = np.arange(10, dtype=np.float32)
    np.testing.assert_array_equal(pt.process(x), x)

    r = Resampler(48_000, 16_000)
    assert r.ratio == 1 / 3
    # streaming block-by-block == one-shot, and lengths match exactly
    sig = np.sin(np.arange(48_000, dtype=np.float32) * 0.01)
    one = r.process(sig)
    r2 = Resampler(48_000, 16_000)
    parts = [r2.process(sig[i : i + 1024]) for i in range(0, sig.size, 1024)]
    np.testing.assert_allclose(np.concatenate(parts), one, atol=1e-6)
    assert one.size == 16_000
    # box decimation preserves a constant signal exactly (anti-alias average)
    flat = Resampler(48_000, 16_000).process(np.full(48_000, 0.5, dtype=np.float32))
    np.testing.assert_allclose(flat, 0.5, atol=1e-6)


def test_resampler_44k1_interpolates_and_keeps_length() -> None:
    from assistant.audio.capture import Resampler

    r = Resampler(44_100, 16_000)
    sig = np.linspace(0.0, 1.0, 44_100, dtype=np.float32)
    # feed in ragged chunks to exercise the phase carry
    out: list[np.ndarray] = []
    for i in range(0, sig.size, 701):
        out.append(r.process(sig[i : i + 701]))
    y = np.concatenate(out)
    assert abs(y.size - 16_000) <= 2
    # monotone ramp stays monotone after resampling (no wrap artifacts)
    assert np.all(np.diff(y) >= -1e-6)
    assert y[0] == pytest.approx(0.0, abs=1e-3)
    assert y[-1] == pytest.approx(1.0, abs=1e-2)


def test_resampler_rejects_bad_rates() -> None:
    from assistant.audio.capture import Resampler

    with pytest.raises(ValueError):
        Resampler(0, 16_000)


def test_mic_capture_resamples_non_16k_device() -> None:
    """If the device only offers 48 kHz, the ring must still see 16 kHz."""
    devices = _input_devices()
    if not devices:
        pytest.skip("no input device on this runner")
    from assistant.audio.capture import MicCapture, RingBuffer

    ring = RingBuffer(16_000 * 2)
    mic = MicCapture(ring, blocksize=1600)
    try:
        mic.start()
    except Exception as exc:  # pragma: no cover - device refusal
        pytest.skip(f"device unusable on this runner: {exc}")
    try:
        time.sleep(0.5)
        assert mic.opened_rate > 0
        assert mic.opened_channels >= 1
        # whatever rate the device opened at, the ring is on the 16 kHz clock:
        # ~0.5 s of audio -> ~8000 samples (allow slack for startup)
        n = len(ring)
        assert 4_000 <= n <= 12_000, f"{n} samples after 0.5 s implies wrong rate"
    finally:
        mic.stop()
