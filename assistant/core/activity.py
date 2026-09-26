"""Local activity log, SQLite, privacy-safe (BUILD_PLAN section 1.3 / 8).

Stores command text, intent, result, and whether data left the PC. Never stores
audio (P1). Rows older than 30 days are pruned on open.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from assistant import paths

_RETENTION_DAYS = 30

_SCHEMA = """
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    utterance TEXT NOT NULL,
    intent TEXT NOT NULL,
    ok INTEGER NOT NULL,
    result TEXT NOT NULL,
    left_pc INTEGER NOT NULL
);
"""


@dataclass(frozen=True, slots=True)
class ActivityRow:
    id: int
    ts: str
    utterance: str
    intent: str
    ok: bool
    result: str
    left_pc: bool


class ActivityLog:
    def __init__(self, db_path: Path | None = None) -> None:
        self._path = db_path if db_path is not None else paths.activity_db_path()
        if self._path.parent != Path("."):
            self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as con:
            con.executescript(_SCHEMA)
            con.execute(
                "DELETE FROM activity WHERE ts < ?",
                (_cutoff_iso(),),
            )

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self._path)
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def record(
        self, utterance: str, intent: str, result: str, ok: bool, left_pc: bool
    ) -> None:
        with self._conn() as con:
            con.execute(
                "INSERT INTO activity (ts, utterance, intent, ok, result, left_pc)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    datetime.now(UTC).isoformat(timespec="seconds"),
                    utterance,
                    intent,
                    int(ok),
                    result,
                    int(left_pc),
                ),
            )

    def recent(self, limit: int = 20) -> list[ActivityRow]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT id, ts, utterance, intent, ok, result, left_pc"
                " FROM activity ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            ActivityRow(
                id=r[0], ts=r[1], utterance=r[2], intent=r[3],
                ok=bool(r[4]), result=r[5], left_pc=bool(r[6]),
            )
            for r in rows
        ]


def _cutoff_iso() -> str:
    from datetime import timedelta

    return (datetime.now(UTC) - timedelta(days=_RETENTION_DAYS)).isoformat(
        timespec="seconds"
    )
