"""Skill contracts: Skill ABC, Result, Risk, Permission (BUILD_PLAN section 6).

``plan()`` computes the exact effect with no side effects; ``PermissionGuard``
reads ``Plan.summary``/``Plan.risk`` and decides confirmation. Skills never
bypass the guard (section 6.3).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from assistant.nlu.schema import Intent


class Risk(StrEnum):
    SAFE = "safe"
    CAREFUL = "careful"
    CONFIRM = "confirm"
    FORBIDDEN = "forbidden"


class Permission(StrEnum):
    """Permission kinds a plan may require (section 6.2)."""

    FS_READ = "fs_read"
    FS_WRITE = "fs_write"
    USB_READ = "usb_read"
    NETWORK = "network"
    ACCOUNT_EMAIL = "account_email"
    ACCOUNT_MESSAGE = "account_message"


@dataclass(frozen=True, slots=True)
class Plan:
    """The exact effect of an intent, computed before any side effect."""

    intent: Intent
    risk: Risk
    summary: str  # what confirmation reads back (S4)
    permissions: tuple[Permission, ...] = ()
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Result:
    """Outcome of a skill execution (section 6.2)."""

    ok: bool
    speech: str  # <= 12 words for local actions
    display: str | None = None
    data: dict[str, Any] | None = None
    left_pc: bool = False


@dataclass(slots=True)
class Context:
    """Everything a skill may use. Filled by the orchestrator; fakes in tests."""

    utterance: str = ""
    followup: bool = False


class Skill(ABC):
    """Base class for all skills."""

    name: str = "skill"
    intents: tuple[str, ...] = ()
    risk: dict[str, Risk] = {}

    @abstractmethod
    async def plan(self, intent: Intent, ctx: Context) -> Plan:
        """Resolve entities and compute the effect. NO side effects."""

    @abstractmethod
    async def execute(self, plan: Plan, ctx: Context) -> Result:
        """Perform the effect (only ever called after the guard approved)."""

    def handles(self, intent_name: str) -> bool:
        return intent_name in self.intents
