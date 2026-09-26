"""Well-known paths for config, logs, models, and databases (BUILD_PLAN section 7).

Everything lives under one app-data root:

* Windows: ``%LOCALAPPDATA%\\PCAssistant``
* other OSes (CI): ``$XDG_DATA_HOME/pc-assistant`` or ``~/.local/share/pc-assistant``

Functions return paths only; nothing here creates directories (see :func:`ensure_dirs`).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "PCAssistant"


def app_data_dir() -> Path:
    """Root directory for config, logs, databases, and downloaded models."""
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        base = Path(local) if local else Path.home() / "AppData" / "Local"
        return base / APP_DIR_NAME
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "pc-assistant"


def config_path() -> Path:
    return app_data_dir() / "config.toml"


def log_dir() -> Path:
    return app_data_dir() / "logs"


def models_dir() -> Path:
    return app_data_dir() / "models"


def activity_db_path() -> Path:
    return app_data_dir() / "activity.db"


def jobs_db_path() -> Path:
    return app_data_dir() / "jobs.db"


def ensure_dirs() -> None:
    """Create the app-data directories we will write to."""
    for d in (app_data_dir(), log_dir(), models_dir()):
        d.mkdir(parents=True, exist_ok=True)
