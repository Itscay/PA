"""Settings window with tabs for all configuration sections (BUILD_PLAN section 8)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from assistant import paths
from assistant.config import AudioConfig, Config, load_config
from assistant.ui.theme import STYLESHEET, apply_dark_theme


class SettingsDialog(QDialog):
    """Settings dialog with tabs matching config.toml sections."""

    config_saved = Signal(Config)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("PC Assistant — Settings")
        self.setMinimumSize(600, 500)
        self.setStyleSheet(STYLESHEET)
        apply_dark_theme(self)

        self._config_path = paths.config_path()
        self._current_config: Config = load_config(self._config_path).config
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Tab widget
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        # Build tabs
        self._build_assistant_tab()
        self._build_audio_tab()
        self._build_nlu_tab()
        self._build_llm_tab()
        self._build_research_tab()
        self._build_permissions_tab()
        self._build_email_tab()
        self._build_messaging_tab()
        self._build_apps_tab()

        # Button box
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._on_apply)
        layout.addWidget(buttons)

    # ---- Tab builders ----

    def _build_assistant_tab(self) -> None:
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(10)

        self._name_edit = QLineEdit()
        self._wake_word_combo = QComboBox()
        self._wake_word_combo.addItems(["hey_jarvis", "hey_assistant", "custom"])
        self._wake_sensitivity = QSpinBox()
        self._wake_sensitivity.setRange(0, 100)
        self._wake_sensitivity.setSuffix("%")
        self._push_to_talk = QLineEdit()
        self._push_to_talk.setPlaceholderText("ctrl+alt+space")
        self._language = QLineEdit()
        self._follow_up = QSpinBox()
        self._follow_up.setRange(1, 30)
        self._follow_up.setSuffix(" s")
        self._speak_confirm = QCheckBox()

        layout.addRow("Assistant Name:", self._name_edit)
        layout.addRow("Wake Word:", self._wake_word_combo)
        layout.addRow("Wake Sensitivity:", self._wake_sensitivity)
        layout.addRow("Push-to-Talk:", self._push_to_talk)
        layout.addRow("Language:", self._language)
        layout.addRow("Follow-up Window:", self._follow_up)
        layout.addRow("Speak Confirmations:", self._speak_confirm)

        self._tabs.addTab(tab, "Assistant")

    def _build_audio_tab(self) -> None:
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(10)

        self._input_device = QComboBox()
        self._input_device.setEditable(True)
        self._refresh_devices_btn = QPushButton("Refresh")
        self._refresh_devices_btn.clicked.connect(self._refresh_input_devices)

        device_layout = QHBoxLayout()
        device_layout.addWidget(self._input_device)
        device_layout.addWidget(self._refresh_devices_btn)

        self._stt_model = QComboBox()
        self._stt_model.addItems(["tiny.en", "base.en", "small.en", "medium.en"])
        self._stt_device = QComboBox()
        self._stt_device.addItems(["auto", "cpu", "cuda"])
        self._tts = QComboBox()
        self._tts.addItems(["sapi", "piper"])
        self._voice = QLineEdit()
        self._voice.setPlaceholderText("SAPI voice name or Piper model path")

        layout.addRow("Input Device:", device_layout)
        layout.addRow("STT Model:", self._stt_model)
        layout.addRow("STT Device:", self._stt_device)
        layout.addRow("TTS Engine:", self._tts)
        layout.addRow("Voice:", self._voice)

        self._tabs.addTab(tab, "Audio")
        self._refresh_input_devices()

    def _build_nlu_tab(self) -> None:
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(10)

        self._local_llm = QComboBox()
        self._local_llm.addItems(["off", "ollama"])
        self._ollama_model = QLineEdit()
        self._cloud_fallback = QCheckBox()

        layout.addRow("Local LLM:", self._local_llm)
        layout.addRow("Ollama Model:", self._ollama_model)
        layout.addRow("Cloud Fallback (off by default):", self._cloud_fallback)

        self._tabs.addTab(tab, "NLU")

    def _build_llm_tab(self) -> None:
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(10)

        self._llm_provider = QComboBox()
        self._llm_provider.addItems(["anthropic", "openai"])
        self._llm_model = QLineEdit()
        self._max_summary = QSpinBox()
        self._max_summary.setRange(20, 500)
        self._max_summary.setSuffix(" words")

        layout.addRow("Provider:", self._llm_provider)
        layout.addRow("Model:", self._llm_model)
        layout.addRow("Max Summary Words:", self._max_summary)

        self._tabs.addTab(tab, "LLM")

    def _build_research_tab(self) -> None:
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(10)

        self._search_provider = QComboBox()
        self._search_provider.addItems(["brave", "tavily"])
        self._results_to_read = QSpinBox()
        self._results_to_read.setRange(1, 10)
        self._open_browser = QComboBox()
        self._open_browser.addItems(["never", "ask", "always"])

        layout.addRow("Search Provider:", self._search_provider)
        layout.addRow("Results to Read:", self._results_to_read)
        layout.addRow("Open Browser:", self._open_browser)

        self._tabs.addTab(tab, "Research")

    def _build_permissions_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        # USB read toggle
        self._usb_read = QCheckBox("Allow reading from USB drives when I ask")
        layout.addWidget(self._usb_read)

        # Allow-list
        group = QGroupBox("Allowed Folders (read_write)")
        group_layout = QVBoxLayout(group)

        self._allow_list = QListWidget()
        self._allow_list.setMinimumHeight(150)
        group_layout.addWidget(self._allow_list)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add Folder…")
        add_btn.clicked.connect(self._add_allow_folder)
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_allow_folder)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()
        group_layout.addLayout(btn_layout)

        layout.addWidget(group)
        layout.addStretch()

        self._tabs.addTab(tab, "Permissions")

    def _build_email_tab(self) -> None:
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(10)

        self._default_account = QComboBox()
        self._default_account.addItems(["gmail", "outlook"])
        self._signature = QLineEdit()

        layout.addRow("Default Account:", self._default_account)
        layout.addRow("Signature:", self._signature)

        self._tabs.addTab(tab, "Email")

    def _build_messaging_tab(self) -> None:
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(10)

        self._telegram = QComboBox()
        self._telegram.addItems(["off", "telethon", "desktop"])
        self._whatsapp = QComboBox()
        self._whatsapp.addItems(["off", "desktop"])

        layout.addRow("Telegram:", self._telegram)
        layout.addRow("WhatsApp:", self._whatsapp)

        self._tabs.addTab(tab, "Messaging")

    def _build_apps_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        self._apps_list = QListWidget()
        self._apps_list.setMinimumHeight(200)
        layout.addWidget(QLabel("App Aliases (spoken name → actual app name):"))
        layout.addWidget(self._apps_list)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add Alias…")
        add_btn.clicked.connect(self._add_app_alias)
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_app_alias)
        refresh_btn = QPushButton("Refresh App Index")
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(remove_btn)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._tabs.addTab(tab, "Apps")

    # ---- Device handling ----

    def _refresh_input_devices(self) -> None:
        import sounddevice as sd
        self._input_device.clear()
        self._input_device.addItem("default", "default")
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0:
                self._input_device.addItem(f"{dev['name']} [{i}]", i)

    # ---- Allow list handling ----

    def _add_allow_folder(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Allow")
        if folder:
            item = QListWidgetItem(folder)
            item.setData(Qt.ItemDataRole.UserRole, "read_write")
            self._allow_list.addItem(item)

    def _remove_allow_folder(self) -> None:
        for item in self._allow_list.selectedItems():
            self._allow_list.takeItem(self._allow_list.row(item))

    # ---- App alias handling ----

    def _add_app_alias(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        spoken, ok1 = QInputDialog.getText(self, "Add App Alias", "Spoken name (e.g. 'code'):")
        if not ok1 or not spoken:
            return
        actual, ok2 = QInputDialog.getText(self, "Add App Alias", "Actual app name or exe path:")
        if not ok2 or not actual:
            return
        item = QListWidgetItem(f"{spoken} → {actual}")
        item.setData(Qt.ItemDataRole.UserRole, (spoken, actual))
        self._apps_list.addItem(item)

    def _remove_app_alias(self) -> None:
        for item in self._apps_list.selectedItems():
            self._apps_list.takeItem(self._apps_list.row(item))

    # ---- Load/Save ----

    def _load_values(self) -> None:
        c = self._current_config
        # Assistant
        self._name_edit.setText(c.assistant.name)
        idx = self._wake_word_combo.findText(c.assistant.wake_word)
        if idx >= 0:
            self._wake_word_combo.setCurrentIndex(idx)
        self._wake_sensitivity.setValue(int(c.assistant.wake_sensitivity * 100))
        self._push_to_talk.setText(c.assistant.push_to_talk)
        self._language.setText(c.assistant.language)
        self._follow_up.setValue(c.assistant.follow_up_seconds)
        self._speak_confirm.setChecked(c.assistant.speak_confirmations)

        # Audio
        idx = self._input_device.findData(c.audio.input_device)
        if idx >= 0:
            self._input_device.setCurrentIndex(idx)
        idx = self._stt_model.findText(c.audio.stt_model)
        if idx >= 0:
            self._stt_model.setCurrentIndex(idx)
        idx = self._stt_device.findText(c.audio.stt_device)
        if idx >= 0:
            self._stt_device.setCurrentIndex(idx)
        idx = self._tts.findText(c.audio.tts)
        if idx >= 0:
            self._tts.setCurrentIndex(idx)
        self._voice.setText(c.audio.voice)

        # NLU
        idx = self._local_llm.findText(c.nlu.local_llm)
        if idx >= 0:
            self._local_llm.setCurrentIndex(idx)
        self._ollama_model.setText(c.nlu.ollama_model)
        self._cloud_fallback.setChecked(c.nlu.cloud_fallback)

        # LLM
        idx = self._llm_provider.findText(c.llm.provider)
        if idx >= 0:
            self._llm_provider.setCurrentIndex(idx)
        self._llm_model.setText(c.llm.model)
        self._max_summary.setValue(c.llm.max_summary_words)

        # Research
        idx = self._search_provider.findText(c.research.search_provider)
        if idx >= 0:
            self._search_provider.setCurrentIndex(idx)
        self._results_to_read.setValue(c.research.results_to_read)
        idx = self._open_browser.findText(c.research.open_browser)
        if idx >= 0:
            self._open_browser.setCurrentIndex(idx)

        # Permissions
        self._usb_read.setChecked(c.permissions.usb_read)
        self._allow_list.clear()
        for entry in c.permissions.allow:
            item = QListWidgetItem(entry.path)
            item.setData(Qt.ItemDataRole.UserRole, entry.mode)
            self._allow_list.addItem(item)

        # Email
        idx = self._default_account.findText(c.email.default_account)
        if idx >= 0:
            self._default_account.setCurrentIndex(idx)
        self._signature.setText(c.email.signature)

        # Messaging
        idx = self._telegram.findText(c.messaging.telegram)
        if idx >= 0:
            self._telegram.setCurrentIndex(idx)
        idx = self._whatsapp.findText(c.messaging.whatsapp)
        if idx >= 0:
            self._whatsapp.setCurrentIndex(idx)

        # Apps
        self._apps_list.clear()
        for spoken, actual in c.apps.aliases.items():
            item = QListWidgetItem(f"{spoken} → {actual}")
            item.setData(Qt.ItemDataRole.UserRole, (spoken, actual))
            self._apps_list.addItem(item)

    def _collect_values(self) -> Config:
        # Helper to get input_device as int or "default"
        input_device_data = self._input_device.currentData()
        if input_device_data is None or input_device_data == "default":
            input_device: int | str = "default"
        else:
            input_device = int(input_device_data)

        return Config(
            assistant=type(self._current_config.assistant)(
                name=self._name_edit.text(),
                wake_word=self._wake_word_combo.currentText(),
                wake_sensitivity=self._wake_sensitivity.value() / 100.0,
                push_to_talk=self._push_to_talk.text(),
                language=self._language.text(),
                follow_up_seconds=self._follow_up.value(),
                speak_confirmations=self._speak_confirm.isChecked(),
            ),
            audio=AudioConfig(
                input_device=input_device,
                stt_model=self._stt_model.currentText(),
                stt_device=self._stt_device.currentText(),  # type: ignore[arg-type]
                tts=self._tts.currentText(),  # type: ignore[arg-type]
                voice=self._voice.text(),
            ),
            nlu=type(self._current_config.nlu)(
                local_llm=self._local_llm.currentText(),  # type: ignore[arg-type]
                ollama_model=self._ollama_model.text(),
                cloud_fallback=self._cloud_fallback.isChecked(),
            ),
            llm=type(self._current_config.llm)(
                provider=self._llm_provider.currentText(),  # type: ignore[arg-type]
                model=self._llm_model.text(),
                max_summary_words=self._max_summary.value(),
            ),
            research=type(self._current_config.research)(
                search_provider=self._search_provider.currentText(),  # type: ignore[arg-type]
                results_to_read=self._results_to_read.value(),
                open_browser=self._open_browser.currentText(),  # type: ignore[arg-type]
            ),
            permissions=type(self._current_config.permissions)(
                usb_read=self._usb_read.isChecked(),
                allow=[],
            ),
            email=type(self._current_config.email)(
                default_account=self._default_account.currentText(),  # type: ignore[arg-type]
                signature=self._signature.text(),
            ),
            messaging=type(self._current_config.messaging)(
                telegram=self._telegram.currentText(),  # type: ignore[arg-type]
                whatsapp=self._whatsapp.currentText(),  # type: ignore[arg-type]
            ),
            apps=type(self._current_config.apps)(
                aliases={},
            ),
            contacts=self._current_config.contacts,
        )

    def _on_apply(self) -> None:
        config = self._collect_values()
        self._save_config(config)
        self._current_config = config
        self.config_saved.emit(config)

    def _on_accept(self) -> None:
        self._on_apply()
        self.accept()

    def _save_config(self, config: Config) -> None:
        import tomllib

        # Read existing file to preserve comments/formatting, or create new
        if self._config_path.exists():
            raw = self._config_path.read_text(encoding="utf-8")
            try:
                data = tomllib.loads(raw)
            except Exception:
                data = {}
        else:
            data = {}

        # Update with new values
        data["assistant"] = config.assistant.model_dump()
        data["audio"] = config.audio.model_dump()
        data["nlu"] = config.nlu.model_dump()
        data["llm"] = config.llm.model_dump()
        data["research"] = config.research.model_dump()
        data["permissions"] = config.permissions.model_dump()
        data["email"] = config.email.model_dump()
        data["messaging"] = config.messaging.model_dump()
        data["apps"] = config.apps.model_dump()
        data["contacts"] = {k: v.model_dump() for k, v in config.contacts.items()}

        # Write back as TOML
        try:
            import tomli_w
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            self._config_path.write_text(tomli_w.dumps(data), encoding="utf-8")
        except ImportError:
            # Fallback: manual TOML write
            lines = []
            for section, values in data.items():
                lines.append(f"[{section}]")
                for k, v in values.items():
                    if isinstance(v, dict):
                        lines.append(f'{k} = {{')
                        for k2, v2 in v.items():
                            lines.append(f'  {k2} = "{v2}"')
                        lines.append('}')
                    elif isinstance(v, list):
                        lines.append(f'{k} = [')
                        for item in v:
                            if isinstance(item, dict):
                                lines.append('  {')
                                for k2, v2 in item.items():
                                    lines.append(f'    {k2} = "{v2}"')
                                lines.append('  }')
                            else:
                                lines.append(f'  "{item}",')
                        lines.append(']')
                    elif isinstance(v, bool):
                        lines.append(f'{k} = {str(v).lower()}')
                    elif isinstance(v, (int, float)):
                        lines.append(f'{k} = {v}')
                    else:
                        lines.append(f'{k} = "{v}"')
                lines.append("")
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            self._config_path.write_text("\n".join(lines), encoding="utf-8")


def show_settings_dialog(parent: QWidget | None = None) -> SettingsDialog | None:
    """Show settings dialog modally."""
    dialog = SettingsDialog(parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog
    return None