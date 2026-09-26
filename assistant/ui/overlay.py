"""Overlay window: frameless, always-on-top panel (BUILD_PLAN section 8)."""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from assistant.ui.theme import (
    ACCENT,
    BG_CARD,
    BG_DARK,
    BORDER,
    GREEN,
    STYLESHEET,
    TEXT_PRIMARY,
)


class OverlayState(Enum):
    HIDDEN = "hidden"
    LISTENING = "listening"
    THINKING = "thinking"
    CONFIRMING = "confirming"
    RESULT = "result"
    DICTATING = "dictating"
    PROGRESS = "progress"


class OverlayWindow(QWidget):
    """Frameless always-on-top overlay showing transcript, intent, confirmation, results."""

    confirm_accepted = Signal()
    confirm_rejected = Signal()
    stop_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        super().__init__(parent, flags)
        self._state = OverlayState.HIDDEN
        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self.hide_overlay)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet(STYLESHEET)
        self._build_ui()
        self.resize(600, 120)
        self._position_bottom_center()

    def _build_ui(self) -> None:
        # Main container with rounded corners
        self._container = QWidget(self)
        self._container.setObjectName("container")
        self._container.setStyleSheet(f"""
            QWidget#container {{
                background-color: {BG_CARD.name()};
                border: 1px solid {BORDER.name()};
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._container)

        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(16, 12, 16, 12)
        container_layout.setSpacing(8)

        # Status row (icon + state label)
        status_layout = QHBoxLayout()
        self._status_icon = QLabel("●")
        self._status_icon.setFixedWidth(20)
        font = QFont("Segoe UI", 11)
        font.setBold(True)
        self._status_icon.setFont(font)
        self._state_label = QLabel("Idle")
        self._state_label.setFont(font)
        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(24, 24)
        self._close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: {TEXT_PRIMARY.name()};
                font-size: 14px;
            }}
            QPushButton:hover {{ background-color: {BG_DARK.name()}; border-radius: 4px; }}
        """)
        self._close_btn.clicked.connect(self.hide_overlay)
        status_layout.addWidget(self._status_icon)
        status_layout.addWidget(self._state_label)
        status_layout.addStretch()
        status_layout.addWidget(self._close_btn)
        container_layout.addLayout(status_layout)

        # Transcript / text display
        self._text_label = QLabel("")
        self._text_label.setWordWrap(True)
        self._text_label.setFont(QFont("Segoe UI", 10))
        self._text_label.setStyleSheet(f"color: {TEXT_PRIMARY.name()};")
        container_layout.addWidget(self._text_label)

        # Confirmation buttons (shown in CONFIRMING state)
        self._confirm_layout = QHBoxLayout()
        self._confirm_layout.setSpacing(12)
        self._confirm_yes = QPushButton("Yes")
        self._confirm_yes.setObjectName("primary")
        self._confirm_yes.setMinimumWidth(80)
        self._confirm_yes.clicked.connect(self.confirm_accepted.emit)
        self._confirm_no = QPushButton("No")
        self._confirm_no.setMinimumWidth(80)
        self._confirm_no.clicked.connect(self.confirm_rejected.emit)
        self._confirm_layout.addStretch()
        self._confirm_layout.addWidget(self._confirm_yes)
        self._confirm_layout.addWidget(self._confirm_no)
        self._confirm_widget = QWidget()
        self._confirm_widget.setLayout(self._confirm_layout)
        self._confirm_widget.hide()
        container_layout.addWidget(self._confirm_widget)

        # Progress bar (shown in PROGRESS state)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.hide()
        container_layout.addWidget(self._progress_bar)

        # Dictation indicator
        self._dictation_label = QLabel("🎙 Dictating…")
        self._dictation_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._dictation_label.setStyleSheet(f"color: {GREEN.name()};")
        self._dictation_label.hide()
        container_layout.addWidget(self._dictation_label)

    def _position_bottom_center(self) -> None:
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - self.width()) // 2
            y = geo.height() - self.height() - 80  # Above taskbar
            self.move(x, y)

    def show_overlay(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def hide_overlay(self) -> None:
        self.hide()
        self._auto_hide_timer.stop()

    def set_state(self, state: OverlayState, text: str = "", auto_hide_ms: int = 0) -> None:
        self._state = state
        self.show_overlay()

        # Update status icon color
        colors = {
            OverlayState.LISTENING: GREEN,
            OverlayState.THINKING: ACCENT,
            OverlayState.CONFIRMING: QColor("#FFB900"),
            OverlayState.RESULT: GREEN,
            OverlayState.DICTATING: GREEN,
            OverlayState.PROGRESS: ACCENT,
        }
        color = colors.get(state, TEXT_PRIMARY)
        self._status_icon.setStyleSheet(f"color: {color.name()};")

        # Update state label
        labels = {
            OverlayState.LISTENING: "Listening…",
            OverlayState.THINKING: "Thinking…",
            OverlayState.CONFIRMING: "Confirm",
            OverlayState.RESULT: "Result",
            OverlayState.DICTATING: "Dictating",
            OverlayState.PROGRESS: "Working…",
        }
        self._state_label.setText(labels.get(state, "Idle"))

        # Update text
        self._text_label.setText(text)

        # Show/hide state-specific widgets
        self._confirm_widget.setVisible(state == OverlayState.CONFIRMING)
        self._progress_bar.setVisible(state == OverlayState.PROGRESS)
        self._dictation_label.setVisible(state == OverlayState.DICTATING)

        # Auto-hide timer
        if auto_hide_ms > 0:
            self._auto_hide_timer.start(auto_hide_ms)
        else:
            self._auto_hide_timer.stop()

    def set_progress(self, value: int) -> None:
        self._progress_bar.setValue(value)

    def set_confirmation_prompt(self, prompt: str) -> None:
        self.set_state(OverlayState.CONFIRMING, prompt)

    def show_result(self, text: str, auto_hide_ms: int = 5000) -> None:
        self.set_state(OverlayState.RESULT, text, auto_hide_ms)

    def show_dictating(self, text: str = "") -> None:
        self.set_state(OverlayState.DICTATING, text)

    def show_listening(self, transcript: str = "") -> None:
        self.set_state(OverlayState.LISTENING, transcript)

    def show_thinking(self) -> None:
        self.set_state(OverlayState.THINKING, "")

    def show_progress(self, text: str = "") -> None:
        self.set_state(OverlayState.PROGRESS, text)