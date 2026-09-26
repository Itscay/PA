"""System tray icon with state-indicating icon and menu (BUILD_PLAN section 8)."""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from assistant.ui.theme import ACCENT, BG_CARD, GREEN, RED, TEXT_PRIMARY


class TrayState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    CONFIRMING = "confirming"
    MUTED = "muted"
    PAUSED = "paused"
    ERROR = "error"


class TrayIcon(QSystemTrayIcon):
    """System tray icon with dynamic state icons and context menu."""

    state_changed = Signal(TrayState)
    quit_requested = Signal()
    settings_requested = Signal()
    permissions_requested = Signal()
    activity_log_requested = Signal()
    mute_toggled = Signal(bool)
    pause_requested = Signal(int)  # hours
    overlay_toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = TrayState.IDLE
        self._muted = False
        self._icons: dict[TrayState, QIcon] = {}
        self._build_icons()
        self._build_menu()
        self.setIcon(self._icons[TrayState.IDLE])
        self.setToolTip("PC Assistant — Idle")
        self.activated.connect(self._on_activated)

    def _build_icons(self) -> None:
        """Generate colored circle icons for each state."""
        size = 22
        colors = {
            TrayState.IDLE: BG_CARD,
            TrayState.LISTENING: GREEN,
            TrayState.THINKING: ACCENT,
            TrayState.CONFIRMING: QColor("#FFB900"),  # amber
            TrayState.MUTED: RED,
            TrayState.PAUSED: QColor("#888888"),
            TrayState.ERROR: RED,
        }
        for state, color in colors.items():
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(2, 2, size - 4, size - 4)
            if state == TrayState.MUTED:
                painter.setPen(TEXT_PRIMARY)
                font = painter.font()
                font.setBold(True)
                font.setPixelSize(14)
                painter.setFont(font)
                painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "🔇")
            painter.end()
            self._icons[state] = QIcon(pixmap)

    def _build_menu(self) -> None:
        menu = QMenu()
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None and isinstance(app, QApplication):
            menu.setStyleSheet(app.styleSheet())

        # State indicator (non-interactive)
        self._state_action = QAction("● Idle", self)
        self._state_action.setEnabled(False)
        menu.addAction(self._state_action)
        menu.addSeparator()

        # Toggle overlay
        self._overlay_action = QAction("Show Overlay", self)
        self._overlay_action.setCheckable(True)
        self._overlay_action.toggled.connect(self.overlay_toggled.emit)
        menu.addAction(self._overlay_action)

        # Mute toggle
        self._mute_action = QAction("Mute Microphone", self)
        self._mute_action.setCheckable(True)
        self._mute_action.toggled.connect(self._on_mute_toggled)
        menu.addAction(self._mute_action)

        menu.addSeparator()

        # Pause submenu
        pause_menu = menu.addMenu("Pause Listening")
        for hours, label in [(1, "1 Hour"), (4, "4 Hours"), (8, "8 Hours"), (24, "24 Hours")]:
            action = QAction(label, self)
            action.triggered.connect(lambda _, h=hours: self.pause_requested.emit(h))
            pause_menu.addAction(action)

        menu.addSeparator()

        # Settings, Permissions, Activity Log
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.settings_requested.emit)
        menu.addAction(settings_action)

        permissions_action = QAction("Permissions", self)
        permissions_action.triggered.connect(self.permissions_requested.emit)
        menu.addAction(permissions_action)

        activity_action = QAction("Activity Log", self)
        activity_action.triggered.connect(self.activity_log_requested.emit)
        menu.addAction(activity_action)

        menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_requested.emit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.overlay_toggled.emit(True)

    def _on_mute_toggled(self, checked: bool) -> None:
        self._muted = checked
        self.mute_toggled.emit(checked)
        self._update_state_display()

    def set_state(self, state: TrayState) -> None:
        self._state = state
        self.setIcon(self._icons[state])
        self._update_state_display()
        self.state_changed.emit(state)

    def _update_state_display(self) -> None:
        label = self._state.value.capitalize()
        if self._muted:
            label += " (Muted)"
        self._state_action.setText(f"● {label}")
        self.setToolTip(f"PC Assistant — {label}")

    def set_overlay_visible(self, visible: bool) -> None:
        self._overlay_action.setChecked(visible)
        self._overlay_action.setText("Hide Overlay" if visible else "Show Overlay")


def create_tray_icon(parent: QWidget | None = None) -> TrayIcon:
    """Factory function to create and show the tray icon."""
    tray = TrayIcon(parent)
    tray.show()
    return tray