# PROGRESS

Last updated: 2026-09-26

## Current state

**Phase 0 (Foundations) is implemented and verified locally on Windows; CI has been written but not yet
run on GitHub, so the Phase 0 acceptance is not fully ticked.** The repo, pyproject (ruff + mypy `--strict`
+ pytest), config/paths/logging, typed event bus, pure state machine (**100% statement + branch coverage**),
SQLite activity log, single-instance lock, fakes, and `python -m assistant --demo` text REPL exist and are
covered by **71 passing tests** (94% overall package coverage), with `ruff check` and `mypy assistant`
clean.

Honest gaps (do not treat as done):

- **CI never executed**: `.github/workflows/ci.yml` is written but has no push has happened yet, so
  "pytest green on both CI OSes" is unverified. Only Windows (Python 3.14) was exercised locally.
- **Python version drift**: local dev ran on 3.14; the CI matrix targets 3.11/3.12. Nothing was tested on
  3.11 itself yet.
- The demo's rule parser (`assistant/demo.py::parse`) is a **placeholder** covering 6 phrase patterns so the
  pipeline can be exercised; the real grammar is Phase 2.
- `PermissionGuard`, `ConfirmationManager`, orchestrator, and real skills from §6 are **not built** (Phase 2/3
  work); the demo fakes confirmation inline.
- No Windows-specific behaviour (mutex branch, `%LOCALAPPDATA%`) beyond unit tests was validated against a
  real second app instance or a real desktop.

Status marks: `[ ]` todo, `[~]` in progress, `[x]` verified (ran it), `[w]` written but not verifiable in
this environment.

---

## Phase checklists (copied from BUILD_PLAN §9)

### Phase 0: Foundations
- [w] Repo, `pyproject.toml` (ruff, mypy, pytest), CI (Windows + Ubuntu), `PROGRESS.md`, README skeleton.
      (Everything except actual CI execution is done; CI yml exists but has never run.)
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
- [ ] Mic capture + ring buffer + device hot-swap.
- [ ] openWakeWord ("hey_jarvis"), sensitivity setting, suppression while TTS speaks.
- [ ] Silero VAD endpointing (start ≤ 300 ms, end after 1.2 s silence, max 8 s).
- [ ] faster-whisper STT (model download with SHA-256, CPU int8, CUDA auto-detect), initial prompt biasing.
- [ ] TTS (SAPI) with barge-in; chime sounds.
- [ ] Push-to-talk hotkey path.
- [ ] Acceptance: fixture WAVs → WER < 10%; live wake→speak→transcript; latency budgets logged; idle CPU
      measured; no audio files on disk.

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

- None yet. (OAuth sign-ins, API keys, USB drive, saying the wake word will be collected here as phases
  reach them.)

## Log (newest first)

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
