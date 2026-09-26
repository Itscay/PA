"""Tests for the Phase 0 fakes themselves (they are test infrastructure)."""

from __future__ import annotations

import pytest

from tests.fakes import (
    FakeClock,
    FakeFS,
    FakeLLM,
    FakeMail,
    FakeMic,
    FakeSearch,
    FakeSTT,
    FakeTTS,
    FakeWindows,
)


def test_fake_mic_records_start_stop() -> None:
    mic = FakeMic(frames=[b"\x00\x01"])
    mic.start()
    assert mic.started
    mic.stop()
    assert mic.stopped == 1 and not mic.started


def test_fake_stt_queues_transcripts() -> None:
    stt = FakeSTT(["hello", "world"])
    assert stt.transcribe(b"a") == "hello"
    assert stt.transcribe(b"b") == "world"
    assert stt.transcribe(b"c") == ""
    assert stt.calls == [b"a", b"b", b"c"]


def test_fake_tts_records() -> None:
    tts = FakeTTS()
    assert tts.last == ""
    tts.speak("hi")
    tts.speak("bye")
    assert tts.spoken == ["hi", "bye"] and tts.last == "bye"


def test_fake_llm_records_prompts_and_queues() -> None:
    llm = FakeLLM(responses=["r1", "r2"])
    assert llm.complete("p1") == "r1"
    assert llm.complete("p2") == "r2"
    assert llm.complete("p3") == ""
    assert llm.prompts == ["p1", "p2", "p3"]


def test_fake_search_records_queries() -> None:
    s = FakeSearch(results=[[{"url": "u", "snippet": "s"}]])
    assert s.search("q") == [{"url": "u", "snippet": "s"}]
    assert s.search("q2") == []
    assert s.queries == ["q", "q2"]


def test_fake_mail_success_and_failure() -> None:
    m = FakeMail()
    assert m.send("a@b.c", "s", "body") is True
    assert m.sent == [{"to": "a@b.c", "subject": "s", "body": "body"}]
    m.fail_with = "Gmail needs you to sign in again."
    assert m.send("x@y.z", "s", "b") is False
    assert len(m.sent) == 1  # nothing new recorded on failure


def test_fake_fs_copy_move_recycle_and_refusal() -> None:
    fs = FakeFS(paths={"E:/Photos", "E:/Photos/a.jpg"}, refuse={"E:/Photos"})
    assert fs.exists("E:/Photos/")
    assert fs.list("E:/Photos") == ["a.jpg"]
    with pytest.raises(PermissionError):
        fs.copy("E:/Photos/a.jpg", "C:/Allowed")
    fs2 = FakeFS(paths={"E:/Photos/a.jpg", "C:/Allowed"})
    fs2.copy("E:/Photos/a.jpg", "C:/Allowed")
    assert fs2.ops == [("copy", "E:/Photos/a.jpg", "C:/Allowed")]
    fs2.move("C:/Allowed/a.jpg", "C:/Dest")
    fs2.recycle("C:/Dest/a.jpg")
    assert [op for op, _, _ in fs2.ops] == ["copy", "move", "recycle"]


def test_fake_windows_tracks_focus() -> None:
    w = FakeWindows()
    w.launch("chrome")
    assert w.focused == "chrome"
    assert w.focus("notepad") is False
    w.launch("notepad")
    assert w.focus("notepad") is True
    w.close("notepad")
    w.minimize("chrome")
    assert w.closed == ["notepad"] and w.minimized == ["chrome"]


def test_fake_clock_advances() -> None:
    c = FakeClock()
    c.advance(1.5)
    c.advance(0.5)
    assert c.now == 2.0
