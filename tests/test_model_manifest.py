"""SHA-256 model manifest tests (BUILD_PLAN section 9/11)."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import pytest

from assistant.model_manifest import (
    MANIFESTS,
    ModelVerificationError,
    ensure_verified,
    sha256_file,
    verify_files,
)


def _write(path: Path, data: bytes) -> None:
    path.write_bytes(data)


def test_manifest_covers_default_model() -> None:
    """The default STT model must be pinned (base.en ships with the app)."""
    assert "base.en" in MANIFESTS
    entry = MANIFESTS["base.en"]
    assert entry["repo_id"] == "Systran/faster-whisper-base.en"
    assert len(str(entry["revision"])) == 40  # git commit hash
    files = entry["files"]
    assert isinstance(files, dict)
    assert {"config.json", "model.bin", "tokenizer.json", "vocabulary.txt"} <= set(files)
    for name, digest in files.items():  # type: ignore[union-attr]
        assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), name


def test_sha256_file(tmp_path: Path) -> None:
    p = tmp_path / "x.bin"
    _write(p, b"hello")
    assert sha256_file(p) == hashlib.sha256(b"hello").hexdigest()


def test_verify_files_ok(tmp_path: Path) -> None:
    _write(tmp_path / "a.bin", b"aaa")
    _write(tmp_path / "b.bin", b"bbb")
    expected = {
        "a.bin": hashlib.sha256(b"aaa").hexdigest(),
        "b.bin": hashlib.sha256(b"bbb").hexdigest(),
    }
    assert verify_files(expected, tmp_path) == []


def test_verify_files_detects_tamper_and_missing(tmp_path: Path) -> None:
    _write(tmp_path / "a.bin", b"aaa")
    _write(tmp_path / "b.bin", b"TAMPERED")
    expected = {
        "a.bin": hashlib.sha256(b"aaa").hexdigest(),
        "b.bin": hashlib.sha256(b"bbb").hexdigest(),
        "c.bin": hashlib.sha256(b"ccc").hexdigest(),
    }
    problems = verify_files(expected, tmp_path)
    assert len(problems) == 2  # tampered b + missing c
    assert any("b.bin" in p for p in problems)
    assert any("c.bin" in p and "missing" in p for p in problems)


def test_ensure_verified_raises_on_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path / "model.bin", b"bad")
    monkeypatch.setitem(
        MANIFESTS,
        "fake-model",
        {"files": {"model.bin": "0" * 64}},
    )
    from assistant.model_manifest import VERIFIED_ONCE

    VERIFIED_ONCE.discard("fake-model")
    with pytest.raises(ModelVerificationError, match="Delete that directory"):
        ensure_verified("fake-model", tmp_path)


def test_ensure_verified_warns_for_unpinned(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from assistant.model_manifest import VERIFIED_ONCE

    VERIFIED_ONCE.discard("totally-new-model")
    with caplog.at_level(logging.WARNING):
        ensure_verified("totally-new-model", tmp_path)
    assert any("no pinned SHA-256 manifest" in r.message for r in caplog.records)
    # second call is a no-op (verified-once cache)
    with caplog.at_level(logging.WARNING):
        caplog.clear()
        ensure_verified("totally-new-model", tmp_path)
    assert not caplog.records


def test_ensure_verified_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path / "model.bin", b"good")
    monkeypatch.setitem(
        MANIFESTS,
        "idem-model",
        {"files": {"model.bin": hashlib.sha256(b"good").hexdigest()}},
    )
    from assistant.model_manifest import VERIFIED_ONCE

    VERIFIED_ONCE.discard("idem-model")
    ensure_verified("idem-model", tmp_path)
    ensure_verified("idem-model", tmp_path)  # cached, no re-hash errors
    VERIFIED_ONCE.discard("idem-model")


def test_real_cached_snapshot_verifies() -> None:
    """The actually-installed base.en cache must match the pinned manifest."""
    import glob

    snaps = glob.glob(
        str(
            Path.home()
            / ".cache/huggingface/hub/models--Systran--faster-whisper-base.en/snapshots/*"
        )
    )
    if not snaps:
        pytest.skip("base.en not downloaded on this machine yet")
    from assistant.model_manifest import VERIFIED_ONCE

    VERIFIED_ONCE.discard("base.en")
    ensure_verified("base.en", Path(snaps[0]))
