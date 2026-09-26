"""Demo pipeline tests: the Phase 0 acceptance path, end to end with fakes."""

from __future__ import annotations

from pathlib import Path

import pytest

from assistant.core.activity import ActivityLog
from assistant.core.state import State
from assistant.demo import DemoPipeline, parse


@pytest.fixture
def pipe(tmp_path: Path) -> DemoPipeline:
    return DemoPipeline(activity=ActivityLog(tmp_path / "activity.db"))


async def test_parse_open(tmp_path: Path) -> None:
    i = parse("open chrome")
    assert i is not None
    assert i.name == "app.open"
    assert i.slots["app"] == "chrome"


async def test_parse_research() -> None:
    i = parse("what is quantum tunnelling")
    assert i is not None
    assert i.name == "research.ask"
    assert "quantum" in i.slots["query"]


async def test_unknown_utterance(pipe: DemoPipeline) -> None:
    res = await pipe.handle("blargh nonsense")
    assert res.intent is None
    assert res.state is State.IDLE or res.state is State.FOLLOW_UP
    assert pipe.tts.last == "Sorry, I didn't get that."
    rows = pipe.activity.recent() if pipe.activity else []
    assert rows and rows[0].intent == "unknown"


async def test_safe_intent_runs_immediately(pipe: DemoPipeline) -> None:
    res = await pipe.handle("open chrome")
    assert res.intent is not None and res.intent.name == "app.open"
    assert res.result is not None and res.result.ok
    assert pipe.tts.last == "Opening chrome."
    assert pipe.windows.open_apps == ["chrome"]
    assert res.state is State.FOLLOW_UP  # follow-up window opened


async def test_confirm_yes_executes(pipe: DemoPipeline) -> None:
    res = await pipe.handle("shut down")
    assert res.state is State.CONFIRMING  # waits for yes/no
    assert res.result is None
    res2 = await pipe.handle("yes")
    assert res2.result is not None and res2.result.ok
    assert "Shutting down" in pipe.tts.last


async def test_confirm_no_cancels(pipe: DemoPipeline) -> None:
    res = await pipe.handle("shut down")
    assert res.state is State.CONFIRMING
    res2 = await pipe.handle("no")
    assert res2.cancelled is True
    assert pipe.tts.last == "Cancelled."
    assert res2.state is State.FOLLOW_UP


async def test_confirm_silence_equivalent_to_no(pipe: DemoPipeline) -> None:
    """An unrelated answer while confirming is treated as not-yes (cancel)."""
    await pipe.handle("shut down")
    res = await pipe.handle("purple monkey dishwasher")
    assert res.cancelled is True


async def test_research_uses_fakes_and_flags_left_pc(tmp_path: Path) -> None:
    from assistant.demo import DemoPipeline as DP
    from tests.fakes import FakeLLM, FakeSearch

    search = FakeSearch(results=[[{"url": "https://x.test", "snippet": "Tunnelling is a thing."}]])
    llm = FakeLLM(responses=["Quantum tunnelling is particles crossing barriers."])
    pipe = DP(search=search, llm=llm, activity=ActivityLog(tmp_path / "a.db"))
    res = await pipe.handle("what is quantum tunnelling")
    assert search.queries == ["quantum tunnelling"]
    assert llm.prompts  # LLM was asked
    assert res.result is not None and res.result.left_pc is True
    rows = pipe.activity.recent()
    assert rows[0].left_pc is True  # privacy: data leaving PC is logged


async def test_research_no_results(tmp_path: Path) -> None:
    from assistant.demo import DemoPipeline as DP
    from tests.fakes import FakeLLM, FakeSearch

    pipe = DP(search=FakeSearch(), llm=FakeLLM(), activity=None)
    res = await pipe.handle("who is the CEO of Nvidia")
    assert res.result is not None
    assert "couldn't find" in res.result.display  # type: ignore[union-attr]


async def test_careful_close_runs_with_announce(pipe: DemoPipeline) -> None:
    res = await pipe.handle("close notepad")
    assert res.result is not None
    assert pipe.windows.closed == ["notepad"]
    assert pipe.tts.last == "Closing notepad."


async def test_full_wake_cycle_transitions(pipe: DemoPipeline) -> None:
    await pipe.handle("open chrome")
    states = [t[1] for t in pipe.transitions]
    assert State.LISTENING in states
    assert State.TRANSCRIBING in states
    assert State.UNDERSTANDING in states
    assert State.EXECUTING in states
    assert State.RESPONDING in states
    assert states[-1] is State.FOLLOW_UP


async def test_activity_log_written(pipe: DemoPipeline) -> None:
    await pipe.handle("open chrome")
    rows = pipe.activity.recent()
    assert rows[0].utterance == "open chrome"
    assert rows[0].intent == "app.open"
    assert rows[0].ok is True
    assert rows[0].left_pc is False
