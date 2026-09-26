"""Pinned SHA-256 manifests for downloaded models (BUILD_PLAN section 9/11).

Phase 11 builds the full model download manager (resume, UI, all sizes).
This module is the verification core: exact file hashes for the model
revisions this project was validated against, checked when a model is first
loaded (once per process).

A mismatch means the cached model differs from what we tested -- we refuse
to load it and say how to fix it (delete the cache entry to re-download).
A model with no manifest yet logs a warning and loads anyway; PROGRESS.md
records which models are pinned.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

log = logging.getLogger(__name__)

#: model name -> pinned upstream + file hashes
MANIFESTS: dict[str, dict[str, object]] = {
    "base.en": {
        "repo_id": "Systran/faster-whisper-base.en",
        "revision": "3d3d5dee26484f91867d81cb899cfcf72b96be6c",
        "files": {
            "config.json": "f3bc3821e9fc76a27bae538e11ae5b677dcdd352b4600429ce7951d398569aeb",
            "model.bin": "2a166925539a16005f14ff328359f9b9adb9dc4fb631bb3b227526862e93e2ef",
            "tokenizer.json": "929c5252409436dce1b38a75d1abbcb5e132d170d8e324e4e04ed915fa2d22df",
            "vocabulary.txt": "ff77588746d3a2595d32ab5b69ffd7b95ce2441ac57533cb66fc3eb575a115cf",
        },
    },
}

#: Silero VAD is pinned in assistant.audio.vad (single file, own downloader).
VERIFIED_ONCE: set[str] = set()


class ModelVerificationError(RuntimeError):
    """Cached model does not match the pinned manifest."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_files(expected: dict[str, str], directory: Path) -> list[str]:
    """Return a list of problems (empty = verified). Missing files count."""
    problems: list[str] = []
    for name, want in sorted(expected.items()):
        path = directory / name
        if not path.exists():
            problems.append(f"{name}: missing")
            continue
        got = sha256_file(path)
        if got != want:
            problems.append(f"{name}: sha256 {got[:16]}... != pinned {want[:16]}...")
    return problems


def ensure_verified(model_name: str, directory: Path) -> None:
    """Verify once per (model, process). Raises on mismatch; warns if unpinned.

    Re-verification can be forced by clearing VERIFIED_ONCE (tests do this).
    """
    if model_name in VERIFIED_ONCE:
        return
    manifest = MANIFESTS.get(model_name)
    if manifest is None:
        log.warning(
            "no pinned SHA-256 manifest for model %r yet -- loading unverified "
            "(pin it in assistant/model_manifest.py)",
            model_name,
        )
        VERIFIED_ONCE.add(model_name)
        return
    problems = verify_files(manifest["files"], directory)  # type: ignore[arg-type]
    if problems:
        raise ModelVerificationError(
            f"whisper model {model_name!r} in {directory} does not match the pinned "
            f"manifest: {'; '.join(problems)}. Delete that directory and re-run to "
            "re-download the verified files."
        )
    VERIFIED_ONCE.add(model_name)
    log.info("verified whisper model %r against pinned SHA-256 manifest", model_name)
