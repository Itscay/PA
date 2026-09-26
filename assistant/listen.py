"""Live listen harness: ``python -m assistant --listen`` (Phase 1 acceptance).

Minimal end-to-end path over the real hardware -- mic capture -> wake word /
push-to-talk -> VAD endpointing -> local STT -> transcript printed. This is
the harness the Phase 1 acceptance checklist runs on ("live: wake -> speak ->
transcript printed"); the full orchestrator with state machine, skills and
overlay arrives in Phase 2.

No audio is written to disk (P1): the mic feeds a RAM ring buffer and the
utterance is passed to STT as an in-memory array.

Controls:
* say the wake word (default "Hey Jarvis"), or press the push-to-talk hotkey
  (default Ctrl+Alt+Space) -> chime, then speak a command
* the utterance ends after 1.2 s of silence (VAD) or 8 s of speech (cap)
* Ctrl+C quits
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Iterator

import numpy as np

from assistant import paths
from assistant.audio import capture
from assistant.audio.chime import ChimePlayer
from assistant.audio.hotkey import PushToTalk
from assistant.audio.stt import FasterWhisper, SttConfig
from assistant.audio.vad import (
    WINDOW_SAMPLES,
    EndpointConfig,
    Endpointer,
    SileroVad,
    VadEvent,
    ensure_model,
)
from assistant.audio.wakeword import OpenWakeWord

log = logging.getLogger(__name__)

WAKE_THRESHOLD = 0.5
SPEECH_WAIT_S = 5.0  # after wake/hotkey: how long to wait for speech to start


class ListenHarness:
    """Drives mic -> wake/hotkey -> VAD -> STT for live verification."""

    def __init__(self, wake_word: str = "hey_jarvis", sensitivity: float = 0.5) -> None:
        self.chime = ChimePlayer()
        self.stt = FasterWhisper(
            SttConfig(
                model="base.en",
                # bias decoding toward app/contact vocabulary (BUILD_PLAN 8.1)
                initial_prompt=(
                    "Open Chrome, close Notepad, Visual Studio Code, CapCut, Telegram. "
                    "Send an email to Sara. Hey Jarvis. Note: buy milk. "
                    "Set volume to thirty. Shut down the computer."
                ),
            )
        )
        self._wake = OpenWakeWord(model_name=wake_word, sensitivity=sensitivity)
        self._vad: SileroVad | None = None
        self._ep = Endpointer(EndpointConfig())
        self._lock = threading.Lock()
        self._listening = False
        self._speech_started = False
        self._utterance: list[np.ndarray] = []
        self._deadline = 0.0
        self.wake_threshold = WAKE_THRESHOLD
        self.transcripts: list[str] = []
        self.wake_count = 0
        self.hotkey_count = 0

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        self._vad = SileroVad(ensure_model(paths.models_dir()))
        self._wake.start()

    def stop(self) -> None:
        self._wake.stop()

    # -- events --------------------------------------------------------------

    def on_hotkey(self) -> None:
        """Push-to-talk pressed: begin listening immediately."""
        with self._lock:
            self.hotkey_count += 1
        self._begin_listening("hotkey")

    def _begin_listening(self, source: str) -> None:
        with self._lock:
            if self._listening:
                return
            self._listening = True
            self._speech_started = False
            self._utterance = []
            self._ep.reset()
            self._deadline = time.monotonic() + SPEECH_WAIT_S
        if source == "wake":
            with self._lock:
                self.wake_count += 1
        print(f"\n[{source}] listening...", flush=True)
        self.chime.play("wake")

    def _finish_listening(self, reason: str) -> np.ndarray | None:
        """Stop listening; returns the utterance when speech actually happened."""
        with self._lock:
            if not self._listening:
                return None
            self._listening = False
            heard_speech = self._speech_started
            parts = self._utterance
            self._utterance = []
        if not heard_speech or not parts:
            print(f"({reason}: no speech heard)", flush=True)
            return None
        return np.concatenate(parts)

    # -- audio callback (mic thread) ------------------------------------------

    def on_audio(self, samples: np.ndarray) -> None:
        score = self._wake.feed(samples)
        if score >= self.wake_threshold:
            self._begin_listening("wake")

        with self._lock:
            listening = self._listening
            if listening:
                self._utterance.append(samples)
        if not listening or self._vad is None:
            return

        for prob in self._frame_probs(samples):
            for ev in self._ep.feed(prob):
                if ev is VadEvent.SPEECH_START:
                    with self._lock:
                        self._speech_started = True
                        self._deadline = (
                            time.monotonic() + EndpointConfig().max_utterance_s
                        )
                elif ev is VadEvent.SPEECH_END:
                    audio = self._finish_listening("vad")
                    self._transcribe(audio)
                    return
        with self._lock:
            timed_out = time.monotonic() > self._deadline
        if timed_out:
            audio = self._finish_listening("timeout")
            self._transcribe(audio)

    def _frame_probs(self, samples: np.ndarray) -> Iterator[float]:
        """Speech probabilities for this mic block (256-sample windows)."""
        assert self._vad is not None
        for i in range(0, len(samples) - WINDOW_SAMPLES + 1, WINDOW_SAMPLES):
            yield float(self._vad.prob(samples[i : i + WINDOW_SAMPLES]))

    def _transcribe(self, audio: np.ndarray | None) -> None:
        if audio is None:
            print("> ", end="", flush=True)
            return
        tr = self.stt.transcribe(audio)
        with self._lock:
            self.transcripts.append(tr.text)
        print(f"transcript ({tr.latency_ms} ms): {tr.text!r}", flush=True)
        print("> ", end="", flush=True)


def run(wake_word: str = "hey_jarvis", sensitivity: float = 0.5) -> int:
    """Run the live harness until Ctrl+C. Returns process exit code."""
    harness = ListenHarness(wake_word=wake_word, sensitivity=sensitivity)

    devices = capture.list_input_devices()
    if not devices:
        print("No microphone input device found.", flush=True)
        return 1

    ring = capture.RingBuffer(capture.SAMPLE_RATE * 12)  # 12 s RAM ring (P1)
    mic = capture.MicCapture(ring, blocksize=1600, on_audio=harness.on_audio)

    hotkey: PushToTalk | None = None
    try:
        hotkey = PushToTalk(on_press=harness.on_hotkey)
        hotkey.start()
    except Exception as exc:
        log.warning("push-to-talk unavailable: %s", exc)

    print("Loading wake word + VAD models...", flush=True)
    try:
        harness.start()
        mic.start()
    except Exception as exc:
        print(f"Failed to start audio: {exc}", flush=True)
        return 1

    print(
        f"Listening. Say the wake word ({wake_word.replace('_', ' ')!r}) or press "
        "Ctrl+Alt+Space, then speak a command. Ctrl+C to quit.",
        flush=True,
    )
    print("> ", end="", flush=True)
    try:
        while True:
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nStopping...", flush=True)
    finally:
        mic.stop()
        harness.stop()
        if hotkey is not None:
            hotkey.stop()
    return 0
