"""Text-to-speech: interface + SAPI (pyttsx3), with barge-in (section 4/9).

While speech plays the engine reports ``speaking`` so the wake word layer can
suppress itself (avoid the assistant waking itself, 3.3). The hotkey calls
``interrupt`` to stop speech immediately (barge-in).

pyttsx3/SAPI quirks handled here (verified empirically on Windows):
* ``runAndWait`` called a second time **on the main thread** after
  ``save_to_file`` hangs forever; ``say`` + ``runAndWait`` cycles fine.
* An engine must be created and used on the **same worker thread**, otherwise
  the first ``runAndWait`` blocks forever.

So this class owns one long-lived worker thread; the engine lives there.
"""

from __future__ import annotations

import logging
import queue
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)


class TextToSpeech(ABC):
    @abstractmethod
    def speak(self, text: str) -> None:
        """Speak ``text`` (blocks until done)."""

    @abstractmethod
    def interrupt(self) -> None:
        """Stop current speech immediately (barge-in)."""

    @property
    @abstractmethod
    def speaking(self) -> bool: ...

    @abstractmethod
    def stop(self) -> None:
        """Shut down the engine."""


class NullTTS(TextToSpeech):
    """Records text instead of speaking; used by --demo and tests."""

    def __init__(self) -> None:
        self.spoken: list[str] = []
        self.interrupts = 0

    def speak(self, text: str) -> None:
        self.spoken.append(text)

    def interrupt(self) -> None:
        self.interrupts += 1

    @property
    def speaking(self) -> bool:
        return False

    def stop(self) -> None:
        pass

    @property
    def last(self) -> str:
        return self.spoken[-1] if self.spoken else ""


class SapiTTS(TextToSpeech):
    """pyttsx3 (SAPI5) on a dedicated worker thread (see module docstring)."""

    def __init__(
        self,
        voice: str = "",
        rate_wpm: int | None = None,
        on_finished: Callable[[], None] | None = None,
        speak_timeout_s: float = 30.0,
    ) -> None:
        self._voice = voice
        self._rate_wpm = rate_wpm
        self._on_finished = on_finished
        self._speak_timeout_s = speak_timeout_s
        self._requests: queue.Queue[tuple[str, threading.Event] | None] = queue.Queue()
        self._speaking = False
        self._lock = threading.Lock()
        self._stopped = False
        self._worker: threading.Thread | None = None
        # pyttsx3 ships no stubs; engine is owned by the worker thread.
        self._engine: Any = None  # set on the worker thread

    def _ensure_worker(self) -> threading.Thread:
        with self._lock:
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(
                    target=self._run, name="tts", daemon=True
                )
                self._worker.start()
            return self._worker

    def _run(self) -> None:
        """Worker thread: owns the engine for its whole life."""
        import pyttsx3

        engine: Any = None
        try:
            engine = pyttsx3.init()
            self._engine = engine
            if self._voice:
                for v in engine.getProperty("voices") or []:
                    if self._voice.lower() in str(v.name).lower():
                        engine.setProperty("voice", v.id)
                        break
            if self._rate_wpm is not None:
                engine.setProperty("rate", self._rate_wpm)
            while True:
                item = self._requests.get()
                if item is None:
                    break
                text, done = item
                with self._lock:
                    self._speaking = True
                try:
                    engine.say(text)
                    engine.runAndWait()
                except Exception:
                    log.exception("TTS failed")
                finally:
                    with self._lock:
                        self._speaking = False
                    done.set()
                    if self._on_finished is not None:
                        try:
                            self._on_finished()
                        except Exception:
                            log.exception("on_finished failed")
        except Exception:
            log.exception("TTS worker crashed")
        finally:
            self._engine = None
            if engine is not None:
                try:
                    engine.stop()
                except Exception:
                    pass

    def speak(self, text: str) -> None:
        """Blocking speak: returns when speech finishes (or the timeout hits).

        The timeout matters when the TTS worker died (e.g. no SAPI engine on
        the machine): without it the caller would block forever.
        """
        if not text or self._stopped:
            return
        done = threading.Event()
        self._ensure_worker()
        self._requests.put((text, done))
        if not done.wait(self._speak_timeout_s):
            log.warning("TTS speak timed out after %.0fs: %r", self._speak_timeout_s, text[:50])

    def speak_async(self, text: str) -> None:
        """Fire-and-forget variant used by the orchestrator."""
        threading.Thread(
            target=lambda: self.speak(text), name="tts-async", daemon=True
        ).start()

    def interrupt(self) -> None:
        """Barge-in: stop the current utterance mid-speech.

        pyttsx3 ``stop()`` from another thread is the documented barge-in
        approach; on this stack it reliably ends ``runAndWait`` early (verified
        on Windows/SAPI5), which unblocks any ``speak`` caller.
        """
        engine = self._engine
        if engine is not None:
            try:
                engine.stop()
            except Exception:
                log.exception("TTS interrupt failed")
        with self._lock:
            self._speaking = False

    @property
    def speaking(self) -> bool:
        with self._lock:
            return self._speaking

    def stop(self) -> None:
        with self._lock:
            if self._stopped:
                return
            self._stopped = True
        self._ensure_worker()
        self._requests.put(None)


def list_voices() -> list[str]:
    """Voices available to Settings -> voice picker."""
    try:
        import pyttsx3

        engine = pyttsx3.init()
        voices = [str(v.name) for v in engine.getProperty("voices") or []]
        engine.stop()
        return voices
    except Exception:
        log.exception("voice enumeration failed")
        return []
