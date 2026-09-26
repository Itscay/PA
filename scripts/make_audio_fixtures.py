"""Generate the committed STT audio fixtures (BUILD_PLAN section 5/9/10).

Run on Windows once:  python scripts/make_audio_fixtures.py

Writes short 16 kHz mono WAVs + manifest.json to tests/audio_fixtures/. The
reference transcripts live in the manifest. Fixtures are *test assets*
committed to the repo (the plan's layout explicitly includes
``tests/audio_fixtures/``); the application itself never writes audio (P1).

pyttsx3/SAPI quirk handled here: multiple ``save_to_file`` calls queued
before a single ``runAndWait``; calling ``runAndWait`` twice hangs forever.
"""

from __future__ import annotations

import json
import pathlib
import sys
import wave

import numpy as np

FIXTURE_DIR = pathlib.Path(__file__).resolve().parent.parent / "tests" / "audio_fixtures"

# (fixture name, reference text) -- commands biased with app/contact names
SENTENCES: list[tuple[str, str]] = [
    ("wake_hey_jarvis", "Hey Jarvis, open Chrome."),
    ("open_chrome", "open chrome"),
    ("close_notepad", "close notepad"),
    ("volume_thirty", "set volume to thirty"),
    ("research_quantum", "what is quantum tunnelling"),
    ("email_sara", "send an email to Sara saying I will be late"),
    ("shut_down", "shut down the computer"),
    ("open_vscode", "open visual studio code"),
    ("note_milk", "note: buy milk"),
    ("long_utternance", "send an email to Sara saying I will be late for the meeting today"),
]


def resample16k(audio: np.ndarray, rate: int) -> np.ndarray:
    if rate == 16_000:
        return audio
    n_out = int(len(audio) * 16_000 / rate)
    return np.interp(
        np.linspace(0, len(audio) - 1, n_out), np.arange(len(audio)), audio
    ).astype(np.float32)


def main() -> int:
    if sys.platform != "win32":
        print("SAPI fixtures require Windows", file=sys.stderr)
        return 2
    import pyttsx3

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    engine = pyttsx3.init()
    # Queue ALL sentences first, then a single runAndWait (hangs otherwise).
    for name, _text in SENTENCES:
        engine.save_to_file(_text, str(FIXTURE_DIR / f"{name}.wav"))
    engine.runAndWait()
    engine.stop()

    manifest: dict[str, str] = {}
    for name, text in SENTENCES:
        path = FIXTURE_DIR / f"{name}.wav"
        if not path.exists():
            print(f"MISSING: {name}", file=sys.stderr)
            return 1
        with wave.open(str(path), "rb") as w:
            rate = w.getframerate()
            channels = w.getnchannels()
            width = w.getsampwidth()
            raw = w.readframes(w.getnframes())
        if width != 2:
            print(f"expected 16-bit PCM for {name}, got width={width}", file=sys.stderr)
            return 1
        samples = np.frombuffer(raw, dtype=np.int16)
        if channels > 1:
            samples = samples.reshape(-1, channels).mean(axis=1).astype(np.int16)
        audio16 = resample16k(samples.astype(np.float32) / 32768.0, rate)
        pcm16 = np.clip(audio16 * 32767, -32768, 32767).astype(np.int16)
        with wave.open(str(path), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(16_000)
            out.writeframes(pcm16.tobytes())
        manifest[f"{name}.wav"] = text
        print(f"{name}.wav  {len(pcm16)/16000:.1f}s  ref={text!r}")

    (FIXTURE_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(manifest)} fixtures + manifest.json to {FIXTURE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
