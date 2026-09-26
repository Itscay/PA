"""Typed event bus (BUILD_PLAN section 3.1/3.2).

Handlers are keyed by the concrete event class, so subscribing to a base class
does not receive subclasses -- keep event types flat. Publishing is synchronous
and thread-safe; a raising handler is logged and skipped so one bad subscriber
cannot break the pipeline.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from assistant.core.state import Effect, State

log = logging.getLogger(__name__)

E = TypeVar("E", bound="Event")


@dataclass(frozen=True, slots=True)
class Event:
    """Base class for all bus events."""


@dataclass(frozen=True, slots=True)
class StateChanged(Event):
    previous: State
    current: State
    effects: tuple[Effect, ...]


@dataclass(frozen=True, slots=True)
class TranscriptUpdated(Event):
    text: str
    final: bool


@dataclass(frozen=True, slots=True)
class IntentReady(Event):
    name: str
    slots: dict[str, Any] = field(default_factory=dict)
    source: str = "rules"


@dataclass(frozen=True, slots=True)
class ResultReady(Event):
    speech: str
    ok: bool = True
    display: str | None = None
    left_pc: bool = False


@dataclass(frozen=True, slots=True)
class ErrorOccurred(Event):
    message: str


Handler = Callable[[Any], None]


class EventBus:
    """Synchronous, thread-safe publish/subscribe keyed by event class."""

    def __init__(self) -> None:
        self._handlers: dict[type[Event], list[Handler]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: type[E], handler: Callable[[E], None]) -> Callable[[], None]:
        """Register a handler; returns an unsubscribe callable."""
        with self._lock:
            self._handlers.setdefault(event_type, []).append(handler)

        def unsubscribe() -> None:
            with self._lock:
                handlers = self._handlers.get(event_type)
                if handlers and handler in handlers:
                    handlers.remove(handler)

        return unsubscribe

    def publish(self, event: Event) -> None:
        """Deliver to handlers of the exact event type. Handler errors are logged."""
        with self._lock:
            handlers = list(self._handlers.get(type(event), ()))
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                log.exception("event handler failed for %s", type(event).__name__)

    def clear(self) -> None:
        with self._lock:
            self._handlers.clear()
