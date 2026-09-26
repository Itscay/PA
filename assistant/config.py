"""Load and validate ``config.toml`` (BUILD_PLAN section 7).

Bad values never crash the app: :func:`load_config` returns defaults plus a list of
human-readable errors (with TOML line numbers where known) so the overlay can show them.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from assistant import paths


class AssistantConfig(BaseModel):
    name: str = "Jarvis"
    wake_word: str = "hey_jarvis"
    wake_sensitivity: float = 0.5
    push_to_talk: str = "ctrl+alt+space"
    language: str = "en"
    follow_up_seconds: int = 5
    speak_confirmations: bool = True

    @field_validator("wake_sensitivity")
    @classmethod
    def _check_sensitivity(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("wake_sensitivity must be between 0 and 1")
        return v


class AudioConfig(BaseModel):
    input_device: str = "default"
    stt_model: str = "base.en"
    stt_device: Literal["auto", "cpu", "cuda"] = "auto"
    tts: Literal["sapi", "piper"] = "sapi"
    voice: str = ""

    @field_validator("stt_model")
    @classmethod
    def _check_stt_model(cls, v: str) -> str:
        allowed = {"tiny.en", "base.en", "small.en", "medium.en"}
        if v not in allowed:
            raise ValueError(f"stt_model must be one of {sorted(allowed)}")
        return v


class NluConfig(BaseModel):
    local_llm: Literal["off", "ollama"] = "off"
    ollama_model: str = ""
    cloud_fallback: bool = False


class LlmConfig(BaseModel):
    provider: Literal["anthropic", "openai"] = "anthropic"
    model: str = ""
    max_summary_words: int = 80


class ResearchConfig(BaseModel):
    search_provider: Literal["brave", "tavily"] = "brave"
    results_to_read: int = 3
    open_browser: Literal["never", "ask", "always"] = "ask"


class AllowEntry(BaseModel):
    path: str
    mode: Literal["read", "read_write"] = "read"
    label: str | None = None


class PermissionsConfig(BaseModel):
    usb_read: bool = False
    allow: list[AllowEntry] = Field(default_factory=list)


class EmailConfig(BaseModel):
    default_account: Literal["gmail", "outlook"] = "gmail"
    signature: str = "\n\nSent by voice"


class MessagingConfig(BaseModel):
    telegram: Literal["off", "telethon", "desktop"] = "off"
    whatsapp: Literal["off", "desktop"] = "off"


class AppsConfig(BaseModel):
    aliases: dict[str, str] = Field(default_factory=dict)


class ContactEntry(BaseModel):
    email: str | None = None
    whatsapp: str | None = None
    telegram: str | None = None


class Config(BaseModel):
    assistant: AssistantConfig = Field(default_factory=AssistantConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    nlu: NluConfig = Field(default_factory=NluConfig)
    llm: LlmConfig = Field(default_factory=LlmConfig)
    research: ResearchConfig = Field(default_factory=ResearchConfig)
    permissions: PermissionsConfig = Field(default_factory=PermissionsConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    messaging: MessagingConfig = Field(default_factory=MessagingConfig)
    apps: AppsConfig = Field(default_factory=AppsConfig)
    contacts: dict[str, ContactEntry] = Field(default_factory=dict)


@dataclass
class LoadResult:
    """Config plus any human-readable load errors (shown in the overlay)."""

    config: Config
    errors: list[str]


def _format_validation_error(exc: ValidationError) -> list[str]:
    out: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "(root)"
        out.append(f"{loc}: {err['msg']}")
    return out


def load_config(path: Path | None = None) -> LoadResult:
    """Load config.toml. Missing file -> defaults; bad file -> defaults + errors."""
    cfg_path = path if path is not None else paths.config_path()
    if not cfg_path.exists():
        return LoadResult(Config(), [])
    try:
        raw_text = cfg_path.read_text(encoding="utf-8")
        data = tomllib.loads(raw_text)
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        return LoadResult(Config(), [f"{cfg_path.name}: {exc}"])
    except OSError as exc:
        return LoadResult(Config(), [f"{cfg_path.name}: {exc}"])
    try:
        return LoadResult(Config.model_validate(data), [])
    except ValidationError as exc:
        return LoadResult(Config(), _format_validation_error(exc))
