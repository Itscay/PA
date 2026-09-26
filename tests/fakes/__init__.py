"""Test fakes (BUILD_PLAN section 5, tests/fakes/).

Duck-typed stand-ins for the real Phase 1+ interfaces (mic, STT, TTS, LLM,
search, mail, filesystem, windows). Every fake records what it was asked to
do so tests can assert on the exact effect.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class FakeMic:
    """Yields scripted frames; records start/stop."""

    def __init__(self, frames: list[bytes] | None = None) -> None:
        self.frames = list(frames or [])
        self.started = False
        self.stopped = 0

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False
        self.stopped += 1


class FakeSTT:
    """Returns queued transcripts in order; records calls."""

    def __init__(self, transcripts: list[str] | None = None) -> None:
        self._queue = list(transcripts or [])
        self.calls: list[bytes] = []

    def transcribe(self, audio: bytes) -> str:
        self.calls.append(audio)
        return self._queue.pop(0) if self._queue else ""


class FakeTTS:
    """Records spoken lines instead of playing them."""

    def __init__(self) -> None:
        self.spoken: list[str] = []

    def speak(self, text: str) -> None:
        self.spoken.append(text)

    @property
    def last(self) -> str:
        return self.spoken[-1] if self.spoken else ""


@dataclass
class FakeLLM:
    """Returns queued completions; records prompts (S2: output is data)."""

    responses: list[str] = field(default_factory=list)
    prompts: list[str] = field(default_factory=list)

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.responses.pop(0) if self.responses else ""


@dataclass
class FakeSearch:
    """Returns queued result lists; records queries."""

    results: list[list[dict[str, str]]] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)

    def search(self, query: str) -> list[dict[str, str]]:
        self.queries.append(query)
        return self.results.pop(0) if self.results else []


@dataclass
class FakeMail:
    """Records sent messages; can be told to fail."""

    sent: list[dict[str, Any]] = field(default_factory=list)
    fail_with: str | None = None

    def send(self, to: str, subject: str, body: str) -> bool:
        if self.fail_with is not None:
            return False
        self.sent.append({"to": to, "subject": subject, "body": body})
        return True


@dataclass
class FakeFS:
    """In-memory filesystem snapshot: exists/list/decision recording.

    Phase 5 replaces the decision logic with the real PermissionGuard path
    checks; this fake only models presence and records requested operations.
    """

    paths: set[str] = field(default_factory=set)
    ops: list[tuple[str, str, str]] = field(default_factory=list)  # (op, src, dst)
    refuse: set[str] = field(default_factory=set)  # paths that raise PermissionError

    def exists(self, path: str | Path) -> bool:
        return str(path).rstrip("/\\") in self.paths

    def list(self, path: str) -> list[str]:
        prefix = str(path).rstrip("/\\") + "/"
        return sorted(
            {p[len(prefix):].split("/", 1)[0] for p in self.paths if p.startswith(prefix)}
        )

    def _denied(self, *paths: str) -> bool:
        """True if any path is inside a refused root (prefix match)."""
        for p in paths:
            norm = str(p).replace("\\", "/").rstrip("/")
            for r in self.refuse:
                root = str(r).replace("\\", "/").rstrip("/")
                if norm == root or norm.startswith(root + "/"):
                    return True
        return False

    def copy(self, src: str, dst: str) -> None:
        if self._denied(src, dst):
            raise PermissionError(f"not allowed: {src} -> {dst}")
        self.ops.append(("copy", src, dst))
        self.paths.add(str(Path(dst) / Path(src).name))

    def move(self, src: str, dst: str) -> None:
        if self._denied(src, dst):
            raise PermissionError(f"not allowed: {src} -> {dst}")
        self.ops.append(("move", src, dst))
        self.paths.discard(src)

    def recycle(self, target: str) -> None:
        if self._denied(target):
            raise PermissionError(f"not allowed: {target}")
        self.ops.append(("recycle", target, ""))
        self.paths.discard(target)


@dataclass
class FakeWindows:
    """Records window/app operations instead of touching the real desktop."""

    open_apps: list[str] = field(default_factory=list)
    focused: str | None = None
    closed: list[str] = field(default_factory=list)
    minimized: list[str] = field(default_factory=list)
    known_apps: list[str] = field(default_factory=list)

    def launch(self, app: str) -> bool:
        self.open_apps.append(app)
        self.focused = app
        return True

    def focus(self, app: str) -> bool:
        if app in self.open_apps:
            self.focused = app
            return True
        return False

    def close(self, window: str) -> None:
        self.closed.append(window)

    def minimize(self, window: str) -> None:
        self.minimized.append(window)


@dataclass
class FakeClock:
    """Deterministic clock for timers (confirm timeout, follow-up window)."""

    now: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def advance(self, seconds: float) -> None:
        with self._lock:
            self.now += seconds
