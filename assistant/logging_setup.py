"""Logging setup: rotating file in the app-data log dir (BUILD_PLAN section 0/9).

Privacy (P1): logs contain command text and errors only -- never audio, never secrets.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from assistant import paths

FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 4


def setup_logging(level: int = logging.INFO, log_dir: Path | None = None) -> Path:
    """Attach a rotating file handler to the root logger. Returns the log file path."""
    target = log_dir if log_dir is not None else paths.log_dir()
    target.mkdir(parents=True, exist_ok=True)
    log_file = target / "assistant.log"

    root = logging.getLogger()
    root.setLevel(level)
    # Idempotent: replace any previous file handler for this path.
    for h in list(root.handlers):
        if isinstance(h, logging.FileHandler) and Path(h.baseFilename) == log_file.resolve():
            root.removeHandler(h)
            h.close()
    handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(FORMAT))
    root.addHandler(handler)
    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
               for h in root.handlers):
        stream = logging.StreamHandler()
        stream.setFormatter(logging.Formatter(FORMAT))
        root.addHandler(stream)
    return log_file
