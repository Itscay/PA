"""Entry point: single-instance lock, logging, then core + UI (or --demo).

Phase 0 ships ``--demo`` only; the real UI and audio pipeline arrive in
Phases 1-2 (BUILD_PLAN section 9).
"""

from __future__ import annotations

import argparse
import logging
import sys

from assistant import __version__, logging_setup, paths
from assistant.single_instance import SingleInstance

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="assistant", description="PC voice assistant")
    parser.add_argument("--version", action="version", version=f"pc-assistant {__version__}")
    parser.add_argument("--demo", action="store_true",
                        help="run the core with fakes and a text REPL (Phase 0)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths.ensure_dirs()
    logging_setup.setup_logging()

    if args.demo:
        from assistant.demo import repl

        repl()
        return 0

    # Phase 1+: real audio pipeline + PySide6 UI. Not built yet (BUILD_PLAN §9).
    with SingleInstance() as lock:
        if not lock.acquired:
            print("PC Assistant is already running.", file=sys.stderr)
            return 1
        print("PC Assistant: audio pipeline and UI arrive in Phase 1-2.", file=sys.stderr)
        print("Use --demo to try the core with fakes meanwhile.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
