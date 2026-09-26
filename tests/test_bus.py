"""Event bus tests."""

from __future__ import annotations

from assistant.core.bus import ErrorOccurred, EventBus, StateChanged, TranscriptUpdated
from assistant.core.state import Effect, State


def test_subscribe_and_publish_by_exact_type() -> None:
    bus = EventBus()
    got: list[StateChanged] = []
    other: list[object] = []
    bus.subscribe(StateChanged, got.append)
    bus.subscribe(ErrorOccurred, other.append)  # type: ignore[arg-type]
    ev = StateChanged(previous=State.IDLE, current=State.LISTENING, effects=(Effect.CHIME,))
    bus.publish(ev)
    assert got == [ev]
    assert other == []


def test_unsubscribe_stops_delivery() -> None:
    bus = EventBus()
    got: list[TranscriptUpdated] = []
    unsub = bus.subscribe(TranscriptUpdated, got.append)
    bus.publish(TranscriptUpdated(text="hi", final=True))
    unsub()
    bus.publish(TranscriptUpdated(text="again", final=True))
    assert len(got) == 1


def test_raising_handler_does_not_break_others() -> None:
    bus = EventBus()
    got: list[TranscriptUpdated] = []

    def boom(_ev: TranscriptUpdated) -> None:
        raise RuntimeError("bad handler")

    bus.subscribe(TranscriptUpdated, boom)
    bus.subscribe(TranscriptUpdated, got.append)
    bus.publish(TranscriptUpdated(text="x", final=True))
    assert len(got) == 1  # second handler still ran


def test_clear_removes_all() -> None:
    bus = EventBus()
    got: list[TranscriptUpdated] = []
    bus.subscribe(TranscriptUpdated, got.append)
    bus.clear()
    bus.publish(TranscriptUpdated(text="x", final=True))
    assert got == []
