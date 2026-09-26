"""Permissions management UI (BUILD_PLAN section 8)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from assistant import paths
from assistant.config import AllowEntry, Config, PermissionsConfig, load_config
from assistant.ui.theme import STYLESHEET, apply_dark_theme


class PermissionsDialog(QDialog):
    """Dialog for managing file system permissions (allow-list, USB)."""

    permissions_changed = Signal(PermissionsConfig)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("File System Permissions")
        self.setMinimumSize(550, 400)
        self.setStyleSheet(STYLESHEET)
        apply_dark_theme(self)

        self._config_path = paths.config_path()
        self._current_config: Config = load_config(self._config_path).config
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Header
        header = QLabel("File System Permissions")
        header.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(header)

        # Explanation
        explanation = QLabel(
            "Voice commands cannot change these settings. "
            "Each change requires a click. The assistant can only access "
            "folders listed below with the specified mode."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #888888;")
        layout.addWidget(explanation)

        # USB read toggle
        self._usb_read = QCheckBox("Allow reading from USB drives when I ask")
        self._usb_read.setToolTip(
            "When enabled, each new USB drive requires one-time confirmation per session "
            "before the assistant can read from it."
        )
        layout.addWidget(self._usb_read)

        # Allow-list
        list_group = QWidget()
        list_layout = QVBoxLayout(list_group)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(8)

        list_header = QHBoxLayout()
        list_header.addWidget(QLabel("Allowed Folders"))
        list_header.addStretch()
        add_btn = QPushButton("Add Folder…")
        add_btn.clicked.connect(self._add_folder)
        list_header.addWidget(add_btn)
        list_layout.addLayout(list_header)

        self._list = QListWidget()
        self._list.setMinimumHeight(200)
        list_layout.addWidget(self._list)

        btn_layout = QHBoxLayout()
        edit_btn = QPushButton("Edit Selected")
        edit_btn.clicked.connect(self._edit_folder)
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_folder)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()
        list_layout.addLayout(btn_layout)

        layout.addWidget(list_group)
        layout.addStretch()

        # Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._on_save)
        btn_box.addWidget(cancel_btn)
        btn_box.addWidget(save_btn)
        layout.addLayout(btn_box)

    def _load_values(self) -> None:
        perms = self._current_config.permissions
        self._usb_read.setChecked(perms.usb_read)
        self._list.clear()
        for entry in perms.allow:
            item = QListWidgetItem(f"{entry.path} [{entry.mode}]")
            if entry.label:
                item.setText(f"{entry.label} — {entry.path} [{entry.mode}]")
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self._list.addItem(item)

    def _add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Allow")
        if not folder:
            return
        self._add_folder_dialog(folder)

    def _add_folder_dialog(self, folder: str, existing: AllowEntry | None = None) -> None:
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit

        dialog = QDialog(self)
        dialog.setWindowTitle("Add Allowed Folder" if existing is None else "Edit Allowed Folder")
        dialog.setStyleSheet(STYLESHEET)
        apply_dark_theme(dialog)

        form = QFormLayout(dialog)
        path_edit = QLineEdit(folder)
        path_edit.setReadOnly(True)
        label_edit = QLineEdit(existing.label if existing else "")
        label_edit.setPlaceholderText("Optional label (e.g., 'Photos', 'Work')")
        mode_combo = QComboBox()
        mode_combo.addItems(["read", "read_write"])
        if existing:
            mode_combo.setCurrentText(existing.mode)

        form.addRow("Path:", path_edit)
        form.addRow("Label:", label_edit)
        form.addRow("Mode:", mode_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            entry = AllowEntry(
                path=path_edit.text(),
                mode=mode_combo.currentText(),  # type: ignore[arg-type]
                label=label_edit.text() or None,
            )
            if existing:
                # Update existing
                for i in range(self._list.count()):
                    item = self._list.item(i)
                    if item.data(Qt.ItemDataRole.UserRole) is existing:
                        item.setData(Qt.ItemDataRole.UserRole, entry)
                        if not entry.label:
                            item.setText(f"{entry.path} [{entry.mode}]")
                        else:
                            item.setText(f"{entry.label} — {entry.path} [{entry.mode}]")
                        break
            else:
                item = QListWidgetItem(f"{entry.path} [{entry.mode}]")
                if entry.label:
                    item.setText(f"{entry.label} — {entry.path} [{entry.mode}]")
                item.setData(Qt.ItemDataRole.UserRole, entry)
                self._list.addItem(item)

    def _edit_folder(self) -> None:
        items = self._list.selectedItems()
        if not items:
            return
        entry = items[0].data(Qt.ItemDataRole.UserRole)
        self._add_folder_dialog(entry.path, existing=entry)

    def _remove_folder(self) -> None:
        items = self._list.selectedItems()
        if not items:
            return
        reply = QMessageBox.question(
            self,
            "Remove Folder",
            f"Remove '{items[0].text()}' from allowed folders?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            for item in items:
                self._list.takeItem(self._list.row(item))

    def _on_save(self) -> None:
        allow = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            entry = item.data(Qt.ItemDataRole.UserRole)
            if entry:
                allow.append(entry)

        new_perms = PermissionsConfig(
            usb_read=self._usb_read.isChecked(),
            allow=allow,
        )

        # Save to config.toml
        self._save_permissions(new_perms)
        self.permissions_changed.emit(new_perms)
        self.accept()

    def _save_permissions(self, perms: PermissionsConfig) -> None:
        import tomllib

        if self._config_path.exists():
            raw = self._config_path.read_text(encoding="utf-8")
            try:
                data = tomllib.loads(raw)
            except Exception:
                data = {}
        else:
            data = {}

        data["permissions"] = perms.model_dump()

        try:
            import tomli_w
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            self._config_path.write_text(tomli_w.dumps(data), encoding="utf-8")
        except ImportError:
            lines = []
            for section, values in data.items():
                lines.append(f"[{section}]")
                for k, v in values.items():
                    if isinstance(v, list):
                        lines.append(f"{k} = [")
                        for item in v:
                            if isinstance(item, dict):
                                lines.append("  {")
                                for k2, v2 in item.items():
                                    if isinstance(v2, str):
                                        lines.append(f'    {k2} = "{v2}"')
                                    elif isinstance(v2, bool):
                                        lines.append(f"    {k2} = {str(v2).lower()}")
                                    else:
                                        lines.append(f"    {k2} = {v2}")
                                lines.append("  }")
                            else:
                                lines.append(f'  "{item}",')
                        lines.append("]")
                    elif isinstance(v, bool):
                        lines.append(f"{k} = {str(v).lower()}")
                    elif isinstance(v, (int, float)):
                        lines.append(f"{k} = {v}")
                    else:
                        lines.append(f'{k} = "{v}"')
                lines.append("")
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            self._config_path.write_text("\n".join(lines), encoding="utf-8")


def show_permissions_dialog(parent: QWidget | None = None) -> PermissionsDialog | None:
    """Show permissions dialog modally."""
    dialog = PermissionsDialog(parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog
    return None