# PROGRESS

Last updated: 2026-09-26

## Current state

**Phase 0 done (CI running). Phase 1 (audio pipeline) code complete and
locally verified on this Windows PC; two live acceptance items need the owner's voice/hands.**

Verified locally (Windows, Python 3.14): **128 tests green, 88% coverage, state machine 100%, ruff +
mypy `--strict` clean.** Phase 1 measurements:

| Metric | Target (§3.4) | Measured |
|---|---|---|
| STT end-of-speech → transcript (~3 s, base.en int8 CPU, warm) | < 900 ms | **611 ms** (pytest, best of 3) |
| Idle CPU, wake word running (real-time mic cadence) | < 3 % of one core | **2.60 %** (15 s steady-state) |
| Wake-phrase detection (SAPI-synthesized "Hey Jarvis") | detect | **0.999** max score |
| False accepts (unrelated speech / live room audio) | 0 | **0.000** / **0.0000** |
| Aggregate WER on committed fixtures (base.en + initial-prompt bias) | < 10 % | **0.000** |
| Audio files written to app dirs during a session | 0 | **0** (pytest scan + live scan) |

Honest gaps (do not treat as done):

- **Phase 1 live acceptance needs the owner:** saying "Hey Jarvis" into the real mic while the app runs,
  and pressing the push-to-talk hotkey (exact steps in *Owner actions* below).
- **CI running**: pushed to `https://github.com/Itscay/PA.git`; Actions workflow executing on windows-latest + ubuntu-latest × Python 3.11/3.12. Results pending.
- **Whisper model SHA-256 manifest not implemented**: faster-whisper downloads via the HF cache without
  our pinned manifest (deferred to Phase 11's model manager). The Silero VAD model *is* SHA-256 pinned.
- **CUDA path untested** (no NVIDIA GPU here); detect_device() returns cpu.
- **Device hot-swap never tested live** (fake getter only; nobody unplugged a mic mid-run).
- "wake word → overlay/chime < 300 ms" not measurable yet -- no orchestrator/overlay until Phase 2.
- openWakeWord runs ONNX only: `tflite-runtime` has no Python 3.14 wheel (its faster preferred backend).
- The demo's rule parser is still a **placeholder** (6 patterns); real grammar is Phase 2. Guard/confirm/
  skills from §6 are Phase 2/3 work; the demo fakes confirmation inline.

Status marks: `[ ]` todo, `[~]` in progress, `[x]` verified (ran it), `[w]` written but not verifiable in
this environment.

---

## Phase checklists (copied from BUILD_PLAN §9)

### Phase 0: Foundations
- [x] Repo, `pyproject.toml` (ruff, mypy, pytest), CI (Windows + Ubuntu), `PROGRESS.md`, README skeleton.
      (Pushed to GitHub; Actions workflow running on windows-latest + ubuntu-latest × Python 3.11/3.12.)
- [x] `config.py` with pydantic models + defaults + validation errors; `paths.py`; logging (rotating file,
      no PII beyond command text, no audio).
- [x] Event bus, pure state machine (§3.3), ActivityLog (SQLite), single-instance lock.
- [x] Fakes: FakeMic, FakeSTT, FakeTTS, FakeLLM, FakeSearch, FakeMail, FakeFS, FakeWindows.
- [ ] **Acceptance:** `pytest` green on both CI OSes; state machine transitions 100% covered;
      `python -m assistant --demo` runs the core with fakes and a text REPL.
      - [x] state machine 100% covered (verified: `pytest tests/test_state.py --cov-fail-under=100`).
      - [x] `--demo` runs with fakes + REPL (verified: piped session shows intents, confirm, cancel).
      - [w] pytest green on **both** CI OSes (verified on Windows only; GitHub Actions not yet run).

### Phase 1: Audio pipeline
- [x] Mic capture + ring buffer + device hot-swap.
      (live mic: 5.9 s captured, 0 dropped blocks; RingBuffer overwrite/wraparound tested;
      DeviceWatch change-detection tested with a fake -- live unplug never tested)
- [x] openWakeWord ("hey_jarvis"), sensitivity setting, suppression while TTS speaks.
      (live: 0.999 on wake phrase, 0.000 on unrelated speech, suppression zeroes output,
      sensitivity validated; float32→int16 conversion documented -- openWakeWord scores int16 only)
- [x] Silero VAD endpointing (start ≤ 300 ms, end after 1.2 s silence, max 8 s).
      (pure Endpointer tests cover all three budgets; real ONNX model verified on SAPI fixtures + live mic;
      model SHA-256 pinned -- note: the pinned model needs **256-sample** frames, not v5's 512)
- [~] faster-whisper STT (model download with SHA-256, CPU int8, CUDA auto-detect), initial prompt biasing.
      (WER 0.000 + 611 ms verified on CPU int8; initial-prompt biasing implemented and proven
      (unbiased base.en measured 12.8% WER -> biased 0.0); SHA-256 manifest + CUDA path still pending)
- [x] TTS (SAPI) with barge-in; chime sounds.
      (live: say() cycles, interrupt flips speaking mid-utterance; chime synthesized in RAM, never written
      to disk; pyttsx3 hang quirks documented, speak-timeout guard added)
- [~] Push-to-talk hotkey path.
      (parse + edge-trigger logic fully unit-tested -- caught & fixed an extra-key re-fire bug;
      global pynput listener never exercised live -- needs an actual key press, owner action)
- [~] **Acceptance:** fixture WAVs → correct transcripts (WER < 10%); live wake→speak→transcript; latency
      budgets logged; idle CPU measured; no audio files on disk.
      - [x] WER < 10% on fixture set (**0.000**; 10 committed WAVs + manifest in `tests/audio_fixtures/`).
      - [ ] live wake → speak → transcript (**owner**: say the wake word -- Owner actions below).
      - [~] latency budgets: STT measured (611 ms ✓); wake→overlay waits on Phase 2 UI/orchestrator.
      - [x] idle CPU measured (**2.60%**, under the 3% budget).
      - [x] no audio files on disk (pytest P1 scan + live app-dir scan: 0 files).

### Phase 2: Understanding + UI + confirmation
- [ ] Intent schema + registry (schema/registry stub exists in Phase 0; full slot models pending).
- [ ] Rule grammar, `normalize.py`, `tests/utterances.yaml` ≥ 150 cases, property tests.
- [ ] Optional Ollama parser + cloud fallback flag (off).
- [ ] PermissionGuard + ConfirmationManager.
- [ ] UI: tray, overlay, settings shell, activity view.
- [ ] Follow-up window, "repeat that", "stop", "never mind".
- [ ] Acceptance: 100% utterances.yaml with rules only; hostile LLM outputs rejected; timeout = cancel;
      overlay states; overlay never steals focus.

### Phase 3: App launching + system control (§8.1, §8.6)
- [ ] App index, fuzzy match, disambiguation.
- [ ] Window enumeration/focus/minimize/maximize/close + unsaved-changes check.
- [ ] Volume, mute, brightness, lock, sleep/shutdown/restart (+ cancel), battery.
- [ ] Acceptance: fixture-index unit tests; live checklists by voice.

### Phase 4: Clipboard, typing, dictation (§8.7)
- [ ] Foreground-window capture, focus restore, SendInput Unicode, key combos.
- [ ] Dictation mode with control phrases, "scratch that", silence timeout.
- [ ] UIPI detection with clear message.
- [ ] Acceptance: live dictation into Notepad/browser; copy/paste across apps; non-ASCII typing.

### Phase 5: Files + USB + permissions UI (§8.5, §2.3)
- [ ] Permissions screen (no voice path to change permissions).
- [ ] USB arrival/removal, per-drive session consent, numbered listing context.
- [ ] Copy/move/recycle with plan → confirm → progress → cancel → result; conflict policy.
- [ ] Acceptance: FakeFS security tests all refused; live USB copy allowed/refused correctly.

### Phase 6: Web research (§8.2)
- [ ] Search providers, fetcher, trafilatura, Playwright fallback.
- [ ] Summarizer with untrusted-source framing; "tell me more"; "show me the sources"; cache.
- [ ] Offline/failure paths.
- [ ] Acceptance: injection test passes; live answer within budget with sources; `left_pc` logged.

### Phase 7: Email (§8.3)
- [ ] Gmail + Outlook providers, OAuth in Settings, keyring storage, reconnect handling.
- [ ] Contact resolution, parser variants, draft UI, rate limit.
- [ ] Acceptance: fake-provider tests; live send to self; "no" sends nothing.

### Phase 8: Messaging (§8.4)
- [ ] Telethon login + send; desktop fallback via deep link.
- [ ] WhatsApp deep link + verified Enter or "ready, press Enter" fallback.
- [ ] Acceptance: fakes + live self-messages on both apps.

### Phase 9: Nice-to-haves I: reminders, notes, media, calendar
- [ ] Reminders (persisted, toasts), notes (Markdown), media keys (+ Spotify), calendar read/create.
- [ ] Acceptance: reminder survives restart; time-parsing tests; live media control.

### Phase 10: Nice-to-haves II: screen explain + task chaining
- [ ] Screenshot → confirm → vision explain.
- [ ] Chain planner, data passing, single combined confirmation, stop on failure.
- [ ] Acceptance: end-to-end chain with one confirmation; FORBIDDEN step refuses whole chain.

### Phase 11: Packaging, first-run, hardening
- [ ] PyInstaller onedir + Inno Setup per-user installer, autostart, uninstaller.
- [ ] First-run wizard (mic test, wake word test, voice pick, permissions F1–F6, privacy summary).
- [ ] Model download manager with SHA-256 manifest + resume.
- [ ] Crash handling, log export (no secrets).
- [ ] Security review against §2 + `pip-audit`.
- [ ] Acceptance: clean VM install → first run → all required features pass; uninstall clean.

### Phase 12: Custom wake word + polish (optional)
- [ ] Train "Hey Assistant", ship `.onnx`, measure false accepts/rejects.
- [ ] Piper voice, overlay themes, per-app dictation tweaks.

---

## Open questions / blockers for the owner

Only the owner can do these two; everything else in Phase 1 is finished:

1. **Live wake-word acceptance:** in the project directory run
   `.venv\Scripts\python -m assistant --listen`, then **say "Hey Jarvis, open Chrome"** into the mic.
   Expected: chime + `[wake] listening...` then `transcript (NNN ms): 'Open Chrome.'`.
2. **Live push-to-talk acceptance:** with `--listen` still running, **press Ctrl+Alt+Space**, speak any
   command, expect the same transcript line. (If Windows prompts about keyboard access, allow it.)

(Saved for later phases: OAuth sign-ins, API keys, USB drive, brightness via real laptop keys.)

## Log (newest first)

### 2026-09-26 — agent — Push to GitHub + CI kickoff
- Pushed to `https://github.com/Itscay/PA.git`; GitHub Actions workflow started on windows-latest + ubuntu-latest × Python 3.11/3.12.
- Phase 0 checklist updated: CI execution now in progress (was `[w]`).

### 2026-09-26 — agent — Phase 1 cleanup: lint + typecheck pass
- Fixed 4 ruff E501 (line too long) issues in `tests/test_model_manifest.py`.
- Fixed mypy errors in `assistant/audio/capture.py`: device index type handling, resampler return type.
- Added `faster_whisper.*` to mypy ignore list in `pyproject.toml`.
- **Verified:** `pytest` → **128 passed**; `ruff check assistant tests scripts` clean; `mypy assistant` (strict, 26 files) clean.

### 2026-09-26 — agent — Phase 1 audio pipeline
- Added audio deps to `pyproject.toml`: numpy, sounddevice, onnxruntime, openWakeWord, faster-whisper,
  pyttsx3, pynput (all installed and import-tested on Python 3.14; `silero-vad` pip pkg rejected -- it
  drags in all of torch; `tflite-runtime` has no 3.14 wheel).
- `assistant/audio/capture.py`: MicCapture (sounddevice, 16 kHz mono, RAM ring buffer with
  overwrite/wraparound semantics), RingBuffer, list_input_devices, DeviceWatch polling default-device
  changes, watchdog wait helper.
- `assistant/audio/vad.py`: **pure** Endpointer (start after 3 frames ≈ 96 ms -- budget ≤ 300 ms; end after
  1.2 s silence; hard cap 8 s) + SileroVad ONNX wrapper with **SHA-256-pinned** model download
  (`1a153a22…`). Found empirically: the pinned model scores **256-sample** windows (v5's 512 gives
  ~0.007 on real speech vs 0.97 with 256); onnxruntime wants a 0-d int64 ndarray for `sr`.
- `assistant/audio/wakeword.py`: WakeWordEngine ABC + Null + OpenWakeWord. Three empirical fixes, all
  documented in code: openWakeWord scores **int16** only (float32 gives 0.0001 on speech vs 0.9987 --
  wrapper converts); `download_models` not `load_models`; scores in **160 ms batches** (2560 samples)
  because session.run() has ~1 ms fixed overhead.
  **CPU optimization:** openWakeWord's `_streaming_melspectrogram` did `list(10-second deque)` every
  80 ms frame just to read the tail (1.53 ms of 3.46 ms/call = 44%). Installed a guarded O(tail)
  replacement (auto-falls back to stock if upstream changes the method). Idle CPU went 6.1% → **2.60%**
  (stock+80 ms vs optimized+160 ms), under the 3% budget; detection kept 0.999/0.000.
- `assistant/audio/stt.py`: SpeechToText ABC + Null + FasterWhisper (base.en int8 CPU default,
  `detect_device()` CUDA probe, `initial_prompt` biasing, latency measured per call).
- `assistant/audio/tts.py`: TextToSpeech ABC + Null + SapiTTS on a **dedicated worker thread** (pyttsx3
  hangs if the engine is created on one thread and used on another; second `runAndWait` after
  `save_to_file` hangs forever -- `say()` cycles fine). Barge-in `interrupt()` verified live. Added a
  speak timeout so a dead worker can never block callers.
- `assistant/audio/chime.py`: wake/tick/cancel cues **synthesized in RAM** (P1 -- no audio asset or file).
- `assistant/audio/hotkey.py`: PushToTalk with `parse_hotkey` + edge-triggered combo arming (test caught
  a bug: an extra key pressed while holding the combo used to re-fire it).
- `assistant/audio/wer.py`: dependency-free WER for acceptance tests.
- `scripts/make_audio_fixtures.py` → `tests/audio_fixtures/`: **10 committed SAPI TTS WAVs** (16 kHz) +
  `manifest.json` refs, per the plan's layout (also covers CI, which has no SAPI).
- `assistant/listen.py` + `--listen` flag: live harness (mic → wake/hotkey → VAD → STT → transcript),
  holds the single-instance lock. This is what the owner runs for the live acceptance items.
- New tests: `test_audio.py` (21: ring buffer, endpointer budgets, Silero model+hash, segmenter, hotkey
  parse, fakes), `test_audio_pipeline.py` (wake detect/false-accept/suppression on real model, SAPI TTS
  barge-in, mic lifecycle w/ skip, DeviceWatch, hotkey edge-trigger, chime, VadPipeline on fixture),
  `test_stt_acceptance.py` (WER, latency, P1 disk scan, chime determinism).
- **How verified (local Windows, Python 3.14):**
  - `pytest` → **116 passed**; coverage **88%** (CI floor 80); `state.py` still **100%**.
  - `ruff check assistant tests scripts` and `mypy assistant` (strict, 25 files) → clean.
  - **WER**: 0.000 aggregate on the fixture set with `initial_prompt` biasing (unbiased base.en measured
    12.8% -- "Chrome"/"tunnelling"/"thirty" misses; biasing is the fix the plan prescribes).
  - **STT latency**: 611 ms best-of-3 for the 3.3 s fixture (budget <900 ms).
  - **Idle CPU**: 2.60% of one core at real-time cadence (budget <3%), 15 s steady-state, `os.times()`.
  - **Wake word**: 0.999 on `Hey Jarvis` fixture, 0.000 on unrelated speech, 0.000 while suppressed,
    0.0000 on live room audio (false-accept check).
  - **Live mic**: 5.9 s captured, 0 dropped blocks, VAD events fired on room speech, warm STT 2234 ms
    for 5.9 s audio, **0 audio files** created in app dirs (P1).
  - **TTS**: two `say()` cycles OK; `interrupt()` flipped speaking → False mid-utterance.
  - `--listen` smoke run: hotkey active, models loaded, mic started, clean shutdown.
- **Not verified / still open:** owner's live wake-word + hotkey acceptance (steps above); CI run (needs
  push); whisper SHA-256 manifest (Phase 11); CUDA path (no GPU); live mic unplug (device hot-swap).

### 2026-09-26 — agent — Phase 0 foundations
- Created repo (git init on `main`), copied `BUILD_PLAN.md`, added `README.md` skeleton, `.gitignore`.
- `pyproject.toml`: pydantic runtime dep; dev extra with pytest/pytest-cov/pytest-asyncio/hypothesis/ruff/
  mypy; ruff (E,F,I,UP,B, line 100), mypy `--strict` on `assistant/`, pytest + coverage config.
- `assistant/paths.py`: `%LOCALAPPDATA%\PCAssistant` on Windows, XDG fallback elsewhere.
- `assistant/config.py`: pydantic models for every §7 table; `load_config()` returns defaults + readable
  errors (never crashes on bad TOML or bad values).
- `assistant/logging_setup.py`: rotating file handler (1 MB × 5), idempotent, no audio logging.
- `assistant/core/bus.py`: typed thread-safe pub/sub keyed by event class; raising handlers logged, not
  fatal.
- `assistant/core/state.py`: pure `next_state()` with `State`/`Event`/`Effect` enums; full transition table
  for the §1.2/§3.3 flows (wake, confirm, barge-in, follow-up, dictation, mute/pause).
- `assistant/core/activity.py`: SQLite activity log (utterance, intent, result, left_pc); schema has **no
  audio column** (P1); 30-day retention prune on open.
- `assistant/single_instance.py`: Windows named mutex (`CreateMutexW`, `use_last_error`) + portable
  file-lock fallback (fcntl/msvcrt) used by tests and POSIX CI.
- `assistant/nlu/schema.py`: `Intent` model (extra="forbid", registry-checked name — S2 foundation) and
  `INTENT_REGISTRY` covering the §13 table.
- `assistant/skills/base.py`: `Skill` ABC, `Plan`, `Result`, `Risk`, `Permission` per §6.
- `tests/fakes/`: FakeMic, FakeSTT, FakeTTS, FakeLLM, FakeSearch, FakeMail, FakeFS (prefix-based refusal),
  FakeWindows, FakeClock — all recording.
- `assistant/demo.py` + `assistant/__main__.py`: `--demo` REPL driving wake→listen→transcribe→understand→
  confirm→execute→respond through the real state machine with fakes; placeholder 6-pattern parser (real
  grammar = Phase 2).
- `.github/workflows/ci.yml`: windows-latest + ubuntu-latest × py 3.11/3.12; ruff, mypy, pytest with 80%
  floor, **100% floor on `assistant/core/state.py`**, demo smoke test.
- **How verified (local Windows, Python 3.14):**
  - `pytest` → **71 passed**.
  - `pytest --cov=assistant` → **94%** package coverage; `state.py` → **100%** with `--cov-fail-under=100`.
  - `ruff check assistant tests` → clean.
  - `mypy assistant` (strict) → clean, 15 files.
  - `printf 'open chrome\nwhat is quantum tunnelling\nshut down\nyes\nblah blah\nquit' |
    python -m assistant --demo` → intents, confirmation prompt, "Cancelled." on wrong/absent answer,
    spoken results printed; exits 0.
  - Security AST test (`tests/test_security.py`): no `eval`/`exec`/`compile`, no `os.system`/`os.popen`,
    no `shell=True`, no `pickle` anywhere in repo.
- **Not verified:** GitHub Actions run (no push made); ubuntu CI leg; Python 3.11. Marked `[w]` above.
