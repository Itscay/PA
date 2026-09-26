"""ActivityLog tests: writes, reads, privacy shape (no audio column)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from assistant.core.activity import ActivityLog


def test_record_and_recent(tmp_path: Path) -> None:
    log = ActivityLog(tmp_path / "activity.db")
    log.record("open chrome", "app.open", "Opening Chrome.", ok=True, left_pc=False)
    log.record("what is x", "research.ask", "A summary.", ok=True, left_pc=True)
    rows = log.recent()
    assert len(rows) == 2
    assert rows[0].utterance == "what is x"  # newest first
    assert rows[0].left_pc is True
    assert rows[1].left_pc is False


def test_schema_has_no_audio_column(tmp_path: Path) -> None:
    db = tmp_path / "activity.db"
    ActivityLog(db)
    con = sqlite3.connect(db)
    cols = {r[1] for r in con.execute("PRAGMA table_info(activity)")}
    con.close()
    assert cols == {"id", "ts", "utterance", "intent", "ok", "result", "left_pc"}
    assert not any("audio" in c or "sound" in c for c in cols)


def test_reopen_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "activity.db"
    ActivityLog(db).record("u", "i", "r", ok=True, left_pc=False)
    log2 = ActivityLog(db)  # CREATE TABLE IF NOT EXISTS must not explode
    assert len(log2.recent()) == 1


def test_limit(tmp_path: Path) -> None:
    log = ActivityLog(tmp_path / "activity.db")
    for i in range(10):
        log.record(f"u{i}", "i", "r", ok=True, left_pc=False)
    assert len(log.recent(limit=3)) == 3
