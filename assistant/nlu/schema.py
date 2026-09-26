"""Intent schema and registry (BUILD_PLAN section 6.1).

Phase 0 ships the contract only: the Intent model, the name registry, and slot
models for the intents the demo pipeline understands. The full rule grammar and
per-intent slot validation land in Phase 2.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

#: Every intent name the assistant may ever emit (BUILD_PLAN section 13).
INTENT_REGISTRY: frozenset[str] = frozenset(
    {
        "app.open",
        "app.focus",
        "app.list",
        "window.close",
        "window.minimize",
        "window.maximize",
        "research.ask",
        "research.more",
        "research.sources",
        "email.send",
        "message.send",
        "files.list",
        "files.copy",
        "files.move",
        "files.recycle",
        "system.volume",
        "system.brightness",
        "system.lock",
        "system.power",
        "system.power_cancel",
        "edit.key",
        "input.type",
        "dictation.start",
        "dictation.stop",
        "clipboard.read",
        "reminder.create",
        "calendar.list",
        "calendar.create",
        "screen.explain",
        "notes.add",
        "media.control",
        "media.now",
        "chain.run",
        "meta.repeat",
        "meta.stop",
        "meta.cancel",
    }
)


class Intent(BaseModel):
    """A parsed utterance. LLM output must validate against this (S2)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    slots: dict[str, Any] = Field(default_factory=dict)
    utterance: str
    source: Literal["rules", "local_llm", "cloud_llm", "ui"] = "rules"
    confidence: float = 1.0

    def model_post_init(self, __context: object) -> None:
        if self.name not in INTENT_REGISTRY:
            raise ValueError(f"unknown intent: {self.name!r}")
