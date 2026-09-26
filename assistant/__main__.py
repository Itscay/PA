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
    parser.add_argument("--listen", action="store_true",
                        help="live mic: wake word / push-to-talk -> VAD -> STT "
                             "transcript (Phase 1 acceptance harness)")
    parser.add_argument("--ui", action="store_true",
                        help="run the PySide6 GUI (tray + overlay + settings)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths.ensure_dirs()
    logging_setup.setup_logging()

    # Single-instance lock for all modes
    with SingleInstance() as lock:
        if not lock.acquired:
            print("PC Assistant is already running.", file=sys.stderr)
            return 1

    if args.demo:
        from assistant.demo import repl

        repl()
        return 0

    if args.listen:
        from assistant.listen import run as listen_run

        # Hold the single-instance lock: two live mic consumers would fight.
        with SingleInstance() as lock:
            if not lock.acquired:
                print("PC Assistant is already running.", file=sys.stderr)
                return 1
        return listen_run()

    if args.ui:
        return run_ui()

    # Default: run UI (Phase 2+)
    return run_ui()


def run_ui() -> int:
    """Run the PySide6 UI with tray, overlay, and audio pipeline."""
    import sys

    try:
        from PySide6.QtWidgets import QApplication

        from assistant.listen import run as listen_run
        from assistant.ui.activity_view import show_activity_log
        from assistant.ui.overlay import OverlayWindow
        from assistant.ui.permissions import show_permissions_dialog
        from assistant.ui.settings import show_settings_dialog
        from assistant.ui.tray import create_tray_icon
    except ImportError as e:
        print(f"PySide6 not available: {e}", file=sys.stderr)
        print("Install with: pip install PySide6", file=sys.stderr)
        return 2

    # Check single instance after PySide6 import
    with SingleInstance() as lock:
        if not lock.acquired:
            print("PC Assistant is already running.", file=sys.stderr)
            return 1

        from typing import cast

        from PySide6.QtWidgets import QApplication
        _app = QApplication.instance()
        if _app is None:
            _app = QApplication(sys.argv)
        app = cast(QApplication, _app)
        app.setQuitOnLastWindowClosed(False)

        # Create tray icon
        tray = create_tray_icon()
        tray.settings_requested.connect(lambda: show_settings_dialog())
        tray.permissions_requested.connect(lambda: show_permissions_dialog())
        tray.activity_log_requested.connect(lambda: show_activity_log())
        tray.quit_requested.connect(app.quit)

        # Create overlay
        overlay = OverlayWindow()
        tray.overlay_toggled.connect(overlay.setVisible)
        overlay.confirm_accepted.connect(lambda: print("User confirmed"))
        overlay.confirm_rejected.connect(lambda: print("User rejected"))
        overlay.stop_requested.connect(lambda: print("User stopped"))

        # Start audio pipeline in background thread
        import threading

        def audio_thread() -> None:
            listen_run(wake_word="hey_jarvis", sensitivity=0.5)

        audio_t = threading.Thread(target=audio_thread, daemon=True)
        audio_t.start()

        return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
