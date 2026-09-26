"""Single-instance lock tests."""

from __future__ import annotations

from pathlib import Path

from assistant.single_instance import SingleInstance


def test_acquire_release(tmp_path: Path) -> None:
    lock = SingleInstance("test_inst_a", lock_file=tmp_path / "a.lock")
    assert lock.acquire() is True
    assert lock.acquired is True
    lock.release()
    assert lock.acquired is False


def test_second_instance_blocked(tmp_path: Path) -> None:
    first = SingleInstance("test_inst_b", lock_file=tmp_path / "b.lock")
    second = SingleInstance("test_inst_b", lock_file=tmp_path / "b.lock")
    assert first.acquire() is True
    assert second.acquire() is False
    first.release()
    # after release, lock is available again
    third = SingleInstance("test_inst_b", lock_file=tmp_path / "b.lock")
    assert third.acquire() is True
    third.release()


def test_context_manager(tmp_path: Path) -> None:
    with SingleInstance("test_inst_c", lock_file=tmp_path / "c.lock") as lock:
        assert lock.acquired is True
    assert lock.acquired is False
    # released on exit -> can re-acquire
    with SingleInstance("test_inst_c", lock_file=tmp_path / "c.lock") as lock2:
        assert lock2.acquired is True


def test_windows_named_mutex_blocks_second(tmp_path: Path) -> None:
    """Default Windows path uses a named mutex (skip on POSIX CI)."""
    import sys

    if sys.platform != "win32":
        import pytest

        pytest.skip("named mutex is Windows-only")
    first = SingleInstance("PCAssistant_test_mutex")
    second = SingleInstance("PCAssistant_test_mutex")
    assert first.acquire() is True
    assert second.acquire() is False
    first.release()
    third = SingleInstance("PCAssistant_test_mutex")
    assert third.acquire() is True
    third.release()
