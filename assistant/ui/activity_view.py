"""Activity log viewer (BUILD_PLAN section 8)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from assistant import paths
from assistant.core.activity import ActivityLog
from assistant.ui.theme import (
    STYLESHEET,
    apply_dark_theme,
)


class ActivityLogDialog(QDialog):
    """Dialog showing the activity log with details."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Activity Log")
        self.setMinimumSize(800, 500)
        self.setStyleSheet(STYLESHEET)
        apply_dark_theme(self)

        self._log = ActivityLog(paths.activity_db_path())
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Header with refresh/export
        header = QHBoxLayout()
        header.addWidget(QLabel("Activity Log"))
        header.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        export_btn = QPushButton("Export…")
        export_btn.clicked.connect(self._export)
        header.addWidget(refresh_btn)
        header.addWidget(export_btn)
        layout.addLayout(header)

        # Splitter: list on left, details on right
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # List
        self._list = QListWidget()
        self._list.setMinimumWidth(300)
        self._list.currentItemChanged.connect(self._on_item_changed)
        splitter.addWidget(self._list)

        # Details
        self._details = QTextEdit()
        self._details.setReadOnly(True)
        self._details.setFontFamily("Consolas")
        self._details.setFontPointSize(9)
        splitter.addWidget(self._details)

        splitter.setSizes([300, 500])

    def _refresh(self) -> None:
        self._list.clear()
        entries = self._log.recent(limit=200)
        for entry in entries:
            ts = entry.ts
            label = f"[{ts}] {entry.intent or '—'} | {entry.result or '—'}"
            if entry.left_pc:
                label += " ☁"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self._list.addItem(item)

    def _on_item_changed(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            self._details.clear()
            return
        entry = current.data(Qt.ItemDataRole.UserRole)
        if entry is None:
            return
        lines = [
            f"Timestamp: {entry.ts}",
            f"Utterance: {entry.utterance}",
            f"Intent: {entry.intent or '—'}",
            f"Slots: {entry.slots or {}}",
            f"Result: {entry.result or '—'}",
            f"Left PC: {'Yes' if entry.left_pc else 'No'}",
            f"Error: {entry.error or '—'}",
        ]
        self._details.setPlainText("\n".join(lines))

    def _export(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Activity Log", "activity_log.txt", "Text Files (*.txt)"
        )
        if path:
            entries = self._log.recent(limit=1000)
            with open(path, "w", encoding="utf-8") as f:
                for e in entries:
                    left = "cloud" if e.left_pc else "local"
                    f.write(f"{e.ts}\t{e.intent or ''}\t{e.utterance}\t{e.result or ''}\t{left}\n")


def show_activity_log(parent: QWidget | None = None) -> None:
    """Show activity log dialog modally."""
    dialog = ActivityLogDialog(parent)
    dialog.exec()