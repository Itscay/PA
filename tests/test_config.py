"""Config loading tests (BUILD_PLAN §7)."""

from __future__ import annotations

from pathlib import Path

from assistant.config import Config, load_config


def test_missing_file_gives_defaults_no_errors(tmp_path: Path) -> None:
    res = load_config(tmp_path / "nope.toml")
    assert res.errors == []
    assert res.config == Config()
    assert res.config.assistant.wake_word == "hey_jarvis"
    assert res.config.audio.stt_model == "base.en"
    assert res.config.permissions.allow == []
    assert res.config.permissions.usb_read is False
    assert res.config.nlu.cloud_fallback is False  # P3: off by default


def test_valid_file_overrides(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    p.write_text(
        """
[assistant]
wake_word = "hey_assistant"
wake_sensitivity = 0.7
follow_up_seconds = 8

[audio]
stt_model = "small.en"

[permissions]
usb_read = true
[[permissions.allow]]
path = "C:\\\\Users\\\\me\\\\Docs"
mode = "read_write"
label = "Docs"

[contacts."mom"]
email = "mom@example.com"
""",
        encoding="utf-8",
    )
    res = load_config(p)
    assert res.errors == []
    assert res.config.assistant.wake_word == "hey_assistant"
    assert res.config.assistant.wake_sensitivity == 0.7
    assert res.config.audio.stt_model == "small.en"
    assert res.config.permissions.usb_read is True
    assert res.config.permissions.allow[0].mode == "read_write"
    assert res.config.contacts["mom"].email == "mom@example.com"


def test_invalid_value_reports_field_not_crash(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    p.write_text('[assistant]\nwake_sensitivity = 1.5\n', encoding="utf-8")
    res = load_config(p)
    assert res.config == Config()  # falls back to defaults
    assert any("wake_sensitivity" in e for e in res.errors)


def test_bad_enum_value_reports_field(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    p.write_text('[audio]\nstt_device = "tpu"\n', encoding="utf-8")
    res = load_config(p)
    assert res.config.audio.stt_device == "auto"
    assert any("stt_device" in e for e in res.errors)


def test_malformed_toml_reports_error(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    p.write_text("[assistant\nbroken", encoding="utf-8")
    res = load_config(p)
    assert res.config == Config()
    assert len(res.errors) == 1
    assert "config.toml" in res.errors[0]


def test_unknown_stt_model_rejected(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    p.write_text('[audio]\nstt_model = "huge.en"\n', encoding="utf-8")
    res = load_config(p)
    assert res.config.audio.stt_model == "base.en"
    assert any("stt_model" in e for e in res.errors)
