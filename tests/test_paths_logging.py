"""paths.py and logging setup tests."""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from assistant import logging_setup, paths


def test_paths_are_stable_and_relative_to_root() -> None:
    root = paths.app_data_dir()
    assert paths.config_path() == root / "config.toml"
    assert paths.log_dir() == root / "logs"
    assert paths.models_dir() == root / "models"
    assert paths.activity_db_path() == root / "activity.db"
    assert paths.jobs_db_path() == root / "jobs.db"


def test_windows_root_uses_localappdata(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\me\AppData\Local")
    root = paths.app_data_dir()
    assert str(root).endswith("PCAssistant")
    assert "AppData" in str(root)


def test_posix_root_uses_xdg(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", "/tmp/xdg")
    root = paths.app_data_dir()
    assert root == Path("/tmp/xdg") / "pc-assistant"


def test_ensure_dirs_creates(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    paths.ensure_dirs()
    assert (tmp_path / "pc-assistant" / "logs").is_dir()
    assert (tmp_path / "pc-assistant" / "models").is_dir()


def test_setup_logging_writes_rotating_file(tmp_path: Path) -> None:
    root = logging.getLogger()
    old_handlers = list(root.handlers)
    try:
        log_file = logging_setup.setup_logging(log_dir=tmp_path)
        logging.getLogger("test").info("hello from test")
        for h in root.handlers:
            h.flush()
        assert log_file.exists()
        assert "hello from test" in log_file.read_text(encoding="utf-8")
        # idempotent: running again must not duplicate the file handler
        def count_file_handlers() -> int:
            return sum(
                1 for h in root.handlers if isinstance(h, logging.handlers.RotatingFileHandler)
            )

        n_before = count_file_handlers()
        logging_setup.setup_logging(log_dir=tmp_path)
        n_after = count_file_handlers()
        assert n_before == n_after
    finally:
        for h in list(root.handlers):
            root.removeHandler(h)
            if isinstance(h, logging.FileHandler):
                h.close()
        for h in old_handlers:
            root.addHandler(h)
