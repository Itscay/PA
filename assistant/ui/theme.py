"""UI theme constants and utilities (BUILD_PLAN section 9)."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QWidget

ACCENT = QColor("#0078D4")  # Windows blue
ACCENT_HOVER = QColor("#106EBE")
ACCENT_PRESSED = QColor("#005A9E")
BG_DARK = QColor("#1F1F1F")
BG_CARD = QColor("#2D2D2D")
BG_HOVER = QColor("#3A3A3A")
TEXT_PRIMARY = QColor("#FFFFFF")
TEXT_SECONDARY = QColor("#CCCCCC")
TEXT_MUTED = QColor("#888888")
BORDER = QColor("#404040")
RED = QColor("#E81123")
GREEN = QColor("#107C10")
AMBER = QColor("#FFB900")


def apply_dark_theme(widget: QWidget) -> None:
    """Apply a consistent dark theme to the widget (or application)."""
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, BG_DARK)
    palette.setColor(QPalette.ColorRole.WindowText, TEXT_PRIMARY)
    palette.setColor(QPalette.ColorRole.Base, BG_CARD)
    palette.setColor(QPalette.ColorRole.AlternateBase, BG_DARK)
    palette.setColor(QPalette.ColorRole.ToolTipBase, BG_CARD)
    palette.setColor(QPalette.ColorRole.ToolTipText, TEXT_PRIMARY)
    palette.setColor(QPalette.ColorRole.Text, TEXT_PRIMARY)
    palette.setColor(QPalette.ColorRole.Button, BG_CARD)
    palette.setColor(QPalette.ColorRole.ButtonText, TEXT_PRIMARY)
    palette.setColor(QPalette.ColorRole.BrightText, RED)
    palette.setColor(QPalette.ColorRole.Link, ACCENT)
    palette.setColor(QPalette.ColorRole.Highlight, ACCENT)
    palette.setColor(QPalette.ColorRole.HighlightedText, TEXT_PRIMARY)
    palette.setColor(QPalette.ColorRole.PlaceholderText, TEXT_MUTED)
    widget.setPalette(palette)

    font = QFont("Segoe UI", 9)
    widget.setFont(font)


# Base64-encoded checkmark SVG for checkboxes
CHECKMARK_SVG = (
    "data:image/svg+xml;base64,"
    "PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUi"
    "IHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xIDQuNUw0LjUg"
    "OEwxMSAxIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJy"
    "b3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8L3N2Zz4K"
)

STYLESHEET = f"""
QToolTip {{
    background-color: {BG_CARD.name()};
    color: {TEXT_PRIMARY.name()};
    border: 1px solid {BORDER.name()};
    padding: 4px 8px;
    border-radius: 4px;
}}

QMenu {{
    background-color: {BG_CARD.name()};
    border: 1px solid {BORDER.name()};
    border-radius: 6px;
    padding: 4px;
}}

QMenu::item {{
    padding: 6px 24px 6px 16px;
    border-radius: 4px;
}}

QMenu::item:selected {{
    background-color: {ACCENT.name()};
}}

QMenu::separator {{
    height: 1px;
    background-color: {BORDER.name()};
    margin: 4px 8px;
}}

QPushButton {{
    background-color: {BG_CARD.name()};
    color: {TEXT_PRIMARY.name()};
    border: 1px solid {BORDER.name()};
    border-radius: 4px;
    padding: 6px 12px;
}}

QPushButton:hover {{
    background-color: {BG_HOVER.name()};
    border-color: {ACCENT.name()};
}}

QPushButton:pressed {{
    background-color: {ACCENT_PRESSED.name()};
}}

QPushButton:disabled {{
    background-color: {BG_DARK.name()};
    color: {TEXT_MUTED.name()};
    border-color: {BORDER.name()};
}}

QPushButton#primary {{
    background-color: {ACCENT.name()};
    border-color: {ACCENT.name()};
}}

QPushButton#primary:hover {{
    background-color: {ACCENT_HOVER.name()};
}}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit {{
    background-color: {BG_CARD.name()};
    color: {TEXT_PRIMARY.name()};
    border: 1px solid {BORDER.name()};
    border-radius: 4px;
    padding: 4px 8px;
    selection-background-color: {ACCENT.name()};
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {{
    border-color: {ACCENT.name()};
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox QAbstractItemView {{
    background-color: {BG_CARD.name()};
    color: {TEXT_PRIMARY.name()};
    border: 1px solid {BORDER.name()};
    selection-background-color: {ACCENT.name()};
}}

QCheckBox, QRadioButton {{
    spacing: 8px;
}}

QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {BORDER.name()};
    border-radius: 3px;
    background-color: {BG_CARD.name()};
}}

QCheckBox::indicator:checked {{
    background-color: {ACCENT.name()};
    border-color: {ACCENT.name()};
    image: url({CHECKMARK_SVG});
}}

QRadioButton::indicator {{
    border-radius: 8px;
}}

QRadioButton::indicator:checked {{
    background-color: {BG_CARD.name()};
    border-color: {ACCENT.name()};
}}

QRadioButton::indicator:checked::before {{
    content: "";
    display: block;
    width: 8px;
    height: 8px;
    margin: 3px;
    border-radius: 4px;
    background-color: {ACCENT.name()};
}}

QScrollBar:vertical {{
    background-color: {BG_DARK.name()};
    width: 8px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: {BORDER.name()};
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {TEXT_MUTED.name()};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background-color: {BG_DARK.name()};
    height: 8px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: {BORDER.name()};
    border-radius: 4px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {TEXT_MUTED.name()};
}}

QGroupBox {{
    border: 1px solid {BORDER.name()};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    color: {TEXT_PRIMARY.name()};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: {TEXT_SECONDARY.name()};
}}

QLabel {{
    color: {TEXT_PRIMARY.name()};
}}

QListWidget, QTreeWidget {{
    background-color: {BG_CARD.name()};
    border: 1px solid {BORDER.name()};
    border-radius: 4px;
    outline: none;
}}

QListWidget::item, QTreeWidget::item {{
    padding: 6px 8px;
    border-radius: 4px;
}}

QListWidget::item:selected, QTreeWidget::item:selected {{
    background-color: {ACCENT.name()};
}}

QListWidget::item:hover, QTreeWidget::item:hover {{
    background-color: {BG_HOVER.name()};
}}

QProgressBar {{
    background-color: {BG_DARK.name()};
    border: 1px solid {BORDER.name()};
    border-radius: 4px;
    text-align: center;
    color: {TEXT_PRIMARY.name()};
}}

QProgressBar::chunk {{
    background-color: {ACCENT.name()};
    border-radius: 3px;
}}

QTabWidget::pane {{
    border: 1px solid {BORDER.name()};
    border-radius: 4px;
    top: -1px;
}}

QTabBar::tab {{
    background-color: {BG_DARK.name()};
    color: {TEXT_SECONDARY.name()};
    padding: 8px 16px;
    border: 1px solid {BORDER.name()};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    background-color: {BG_CARD.name()};
    color: {TEXT_PRIMARY.name()};
    border-color: {BORDER.name()};
}}

QTabBar::tab:hover:!selected {{
    background-color: {BG_HOVER.name()};
}}
"""