"""UI package: tray, overlay, settings, permissions, activity view."""

from __future__ import annotations

from .activity_view import ActivityLogDialog, show_activity_log
from .overlay import OverlayState, OverlayWindow
from .permissions import PermissionsDialog, show_permissions_dialog
from .settings import SettingsDialog, show_settings_dialog
from .theme import ACCENT, BG_CARD, BG_DARK, GREEN, RED, STYLESHEET, TEXT_PRIMARY, apply_dark_theme
from .tray import TrayIcon, TrayState, create_tray_icon

__all__ = [
    "TrayIcon",
    "TrayState",
    "create_tray_icon",
    "OverlayWindow",
    "OverlayState",
    "SettingsDialog",
    "show_settings_dialog",
    "PermissionsDialog",
    "show_permissions_dialog",
    "ActivityLogDialog",
    "show_activity_log",
    "apply_dark_theme",
    "STYLESHEET",
    "ACCENT",
    "BG_CARD",
    "BG_DARK",
    "GREEN",
    "RED",
    "TEXT_PRIMARY",
]