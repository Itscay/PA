# PC Assistant

A Windows desktop voice assistant: local wake word, local speech-to-text, and actions on apps, the web,
email, messaging, files, and the OS — with short spoken confirmations and no destructive action without a
"yes".

**Status: Phase 0 (foundations).** See [BUILD_PLAN.md](BUILD_PLAN.md) for the full spec and
[PROGRESS.md](PROGRESS.md) for what is verified vs. still to do.

## Privacy (non-negotiable)

- Wake word, VAD, and speech-to-text run **locally**; audio is never written to disk.
- Secrets live in Windows Credential Manager, never in config files or logs.
- Cloud LLM calls happen only for web-research summaries and features you explicitly opt into; every call
  is logged with what was sent.

## Quick start (development)

```bash
python -m venv .venv
.venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest                    # unit tests
python -m assistant --demo  # text REPL over the core with fakes
```

## Commands

_(Filled in as features land; each verified phrase is listed here per BUILD_PLAN §10.)_

## Building / installing

_(Phase 11: PyInstaller + Inno Setup.)_
