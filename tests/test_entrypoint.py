"""Entry point and REPL tests (Phase 0 acceptance: --demo runs)."""

from __future__ import annotations

import io
from contextlib import redirect_stdout

import pytest

from assistant.__main__ import build_parser, main


def test_parser_demo_flag() -> None:
    args = build_parser().parse_args(["--demo"])
    assert args.demo is True
    args2 = build_parser().parse_args([])
    assert args2.demo is False


def test_main_demo_runs_repl(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    answers = iter(["open chrome", "shut down", "no", "quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    code = main(["--demo"])
    assert code == 0
    out = capsys.readouterr().out
    assert "intent: app.open" in out
    assert "confirm:" in out
    assert "cancelled" in out


def test_main_demo_eof_exits_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    def eof(_prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", eof)
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert main(["--demo"]) == 0
    assert "Bye" in buf.getvalue()


def test_main_demo_unknown_and_research(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    answers = iter(["gobbledygook", "what is photosynthesis", "quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Sorry, I didn't get that." in out
    assert "research.ask" in out


def test_main_second_instance_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    from assistant.single_instance import SingleInstance

    # SingleInstance() default name == what main() uses
    blocker = SingleInstance()
    assert blocker.acquire() is True
    try:
        # Mock stdin to avoid blocking on input()
        monkeypatch.setattr("builtins.input", lambda _prompt="": "quit")
        code = main(["--demo"])
        assert code == 1
    finally:
        blocker.release()
