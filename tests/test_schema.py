"""Intent schema tests (BUILD_PLAN §6.1, S2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from assistant.nlu.schema import INTENT_REGISTRY, Intent


def test_registry_matches_appendix() -> None:
    # spot-check the §13 table; registry must be non-trivial
    for name in ("app.open", "research.ask", "email.send", "system.power",
                 "files.copy", "meta.cancel", "chain.run"):
        assert name in INTENT_REGISTRY
    assert len(INTENT_REGISTRY) >= 30


def test_valid_intent() -> None:
    i = Intent(name="app.open", slots={"app": "chrome"}, utterance="open chrome")
    assert i.source == "rules"
    assert i.confidence == 1.0


def test_unknown_intent_rejected() -> None:
    with pytest.raises(ValueError, match="unknown intent"):
        Intent(name="run.shell", utterance="run cmd")


def test_extra_fields_rejected() -> None:
    """S2: LLM output with extra fields must be rejected."""
    with pytest.raises(ValidationError):
        Intent(name="app.open", utterance="x", tools=[{"name": "shell"}])  # type: ignore[call-arg]


def test_bad_source_rejected() -> None:
    with pytest.raises(ValidationError):
        Intent(name="app.open", utterance="x", source="llm_hallucination")  # type: ignore[arg-type]
