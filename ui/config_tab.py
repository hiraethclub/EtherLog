"""
Tab 4 – Configuration

Organised sections: Sender Profiles, Report Template, Default Equipment,
Visible Fields, EIBI Autofill, SMTP Settings, Appearance.

Changes are saved immediately.  SMTP password uses keyring with file fallback.
"""

from __future__ import annotations

from typing import Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QTextEdit, QPushButton, QCheckBox, QComboBox,
    QListWidget, QListWidgetItem, QGroupBox, QScrollArea,
    QFrame, QMessageBox, QSpinBox, QDialog, QDialogButtonBox,
    QSplitter, QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal

from models import AppConfig, SenderProfile, SMTPConfig, OPTIONAL_FIELD_LABELS
from data import log_store
import config as cfg_module
from email_handler import TestConnectionWorker


class ProfileDialog(QDialog):
    """Add or edit a sender profile."""

    def __init__(self, profile: Optional[SenderProfile] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Sender Profile" if profile else "Add Sender Profile")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._name = QLineEdit(profile.name if profile else "")
        form.addRow("Full Name *:", self._name)

        self._location = QLineEdit(profile.location if profile else "")
        form.addRow("Location:", self._location)

        self._email = QLineEdit(profile.email if profile else "")
        form.addRow("Email Address *:", self._email)

        self._listener = QLineEdit(profile.listener_number if profile else "")
        form.addRow("Listener / Membership Number:", self._listener)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self):
        if not self._name.text().strip() or not self._email.text().strip():
            QMessageBox.warning(self, "Required Fields", "Full Name and Email are required.")
            return
        self.accept()

    def values(self) -> dict:
        return {
            "name": self._name.text().strip(),
            "location": self._location.text().strip(),
            "email": self._email.text().strip(),
            "listener_number": self._listener.text().strip(),
        }


class ConfigTab(QWidget):
    config_changed = pyqtSignal(object)  # emits updated AppConfig

    def __init__(self, app_config: AppConfig, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._config = app_config
        self._test_worker: Optional[TestConnectionWorker] = None
        self._keyring_ok = cfg_module.keyring_available()
        # Suppress _save() while _load_into_ui() is running.  Without this,
        # textChanged / stateChanged signals fire during programmatic widget
        # population and write half-initialised values back into self._config
        # (e.g. eibi_autofill gets set to False because the checkbox hasn't
        # been set to True yet when the preamble text field emits textChanged).
        self._loading = True
        self._build_ui()
        self._load_into_ui()
        self._loading = False

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        main = QVBoxLayout(container)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(16)

        main.addWidget(self._build_profiles_section())
        main.addWidget(self._build_template_section())
        main.addWidget(self._build_equipment_section())
        main.addWidget(self._build_visible_fields_section())
        main.addWidget(self._build_eibi_section())
        main.addWidget(self._build_smtp_section())
        main.addWidget(self._build_appearance_section())
        main.addStretch()

    # ---- Profiles ----

    def _build_profiles_section(self) -> QGroupBox:
        box = QGroupBox("Sender Profiles")
        layout = QHBoxLayout(box)

        self._profile_list = QListWidget()
        self._profile_list.setMaximumHeight(140)
        layout.addWidget(self._profile_list, 1)

        btn_col = QVBoxLayout()
        layout.addLayout(btn_col)

        add_btn = QPushButton("Add…")
        add_btn.clicked.connect(self._on_add_profile)
        btn_col.addWidget(add_btn)

        edit_btn = QPushButton("Edit…")
        edit_btn.clicked.connect(self._on_edit_profile)
        btn_col.addWidget(edit_btn)

        del_btn = QPushButton("Delete")
        del_btn.clicked.connect(self._on_delete_profile)
        btn_col.addWidget(del_btn)

        activate_btn = QPushButton("Set Active")
        activate_btn.clicked.connect(self._on_activate_profile)
        btn_col.addWidget(activate_btn)

        btn_col.addStretch()
        return box

    # ---- Report template ----

    def _build_template_section(self) -> QGroupBox:
        box = QGroupBox("Report Template")
        form = QFormLayout(box)

        self._salutation_edit = QLineEdit()
        self._salutation_edit.editingFinished.connect(self._save)
        form.addRow("Salutation:", self._salutation_edit)

        self._preamble_edit = QTextEdit()
        self._preamble_edit.setFixedHeight(60)
        self._preamble_edit.textChanged.connect(self._save)
        form.addRow("Preamble:", self._preamble_edit)

        self._closing_edit = QLineEdit()
        self._closing_edit.editingFinished.connect(self._save)
        form.addRow("Closing:", self._closing_edit)

        self._signature_edit = QTextEdit()
        self._signature_edit.setFixedHeight(80)
        self._signature_edit.textChanged.connect(self._save)
        form.addRow("Email Signature:", self._signature_edit)

        return box

    # ---- Default equipment ----

    def _build_equipment_section(self) -> QGroupBox:
        box = QGroupBox("Default Equipment")
        form = QFormLayout(box)

        self._recv_edit = QLineEdit()
        self._recv_edit.editingFinished.connect(self._save)
        form.addRow("Receiver:", self._recv_edit)

        self._ant_edit = QLineEdit()
        self._ant_edit.editingFinished.connect(self._save)
        form.addRow("Antenna:", self._ant_edit)

        self._sw_edit = QLineEdit()
        self._sw_edit.editingFinished.connect(self._save)
        form.addRow("Software:", self._sw_edit)

        self._os_edit = QLineEdit()
        self._os_edit.editingFinished.connect(self._save)
        form.addRow("Operating System:", self._os_edit)

        return box

    # ---- Visible fields ----

    def _build_visible_fields_section(self) -> QGroupBox:
        box = QGroupBox("Visible Fields in New Report")
        layout = QVBoxLayout(box)
        layout.addWidget(QLabel("Uncheck to hide a field in the New Report form:"))

        self._field_checks: dict[str, QCheckBox] = {}
        grid_widget = QWidget()
        grid = QHBoxLayout(grid_widget)
        col_widgets = [QVBoxLayout(), QVBoxLayout()]
        for i, (key, label) in enumerate(OPTIONAL_FIELD_LABELS.items()):
            cb = QCheckBox(label)
            cb.stateChanged.connect(self._on_field_visibility_changed)
            self._field_checks[key] = cb
            col_widgets[i % 2].addWidget(cb)
        for col in col_widgets:
            col.addStretch()
            w = QWidget()
            w.setLayout(col)
            grid.addWidget(w)
        layout.addWidget(grid_widget)
        return box

    # ---- EIBI autofill ----

    def _build_eibi_section(self) -> QGroupBox:
        box = QGroupBox("EIBI Autofill")
        layout = QVBoxLayout(box)
        self._autofill_cb = QCheckBox(
            "Automatically fill Frequency, Language and Target Region when a station "
            "is selected from autocomplete"
        )
        self._autofill_cb.stateChanged.connect(self._save)
        layout.addWidget(self._autofill_cb)
        return box

    # ---- SMTP ----

    def _build_smtp_section(self) -> QGroupBox:
        box = QGroupBox("SMTP Settings")
        form = QFormLayout(box)

        self._smtp_host = QLineEdit()
        self._smtp_host.editingFinished.connect(self._save)
        form.addRow("SMTP Host:", self._smtp_host)

        self._smtp_port = QSpinBox()
        self._smtp_port.setRange(1, 65535)
        self._smtp_port.setValue(587)
        self._smtp_port.editingFinished.connect(self._save)
        form.addRow("SMTP Port:", self._smtp_port)

        self._smtp_user = QLineEdit()
        self._smtp_user.editingFinished.connect(self._save)
        form.addRow("Username:", self._smtp_user)

        self._smtp_pass = QLineEdit()
        self._smtp_pass.setEchoMode(QLineEdit.Password)
        self._smtp_pass.editingFinished.connect(self._on_password_changed)
        form.addRow("Password:", self._smtp_pass)

        if not self._keyring_ok:
            import config as _cfg
            if not _cfg._KEYRING_IMPORTABLE:
                warn_text = (
                    "<b>keyring not installed.</b> Run <code>pip install keyring</code> "
                    "to enable secure password storage. Until then the password will be "
                    "stored in the config file with your explicit consent."
                )
            else:
                warn_text = (
                    "<b>Warning:</b> Secure keychain storage is unavailable on this system. "
                    "The password will be stored in the config file if you choose to save it. "
                    "See README for details."
                )
            warn = QLabel(warn_text)
            warn.setWordWrap(True)
            warn.setStyleSheet("color: #a0522d; background: #fff8dc; padding: 4px;")
            form.addRow("", warn)

        self._tls_cb = QCheckBox("Use STARTTLS")
        self._tls_cb.stateChanged.connect(self._save)
        form.addRow("", self._tls_cb)

        self._ssl_cb = QCheckBox("Use SSL (port 465)")
        self._ssl_cb.stateChanged.connect(self._save)
        form.addRow("", self._ssl_cb)

        self._self_signed_cb = QCheckBox("Accept self-signed certificates")
        self._self_signed_cb.setToolTip(
            "Disable SSL certificate verification.\n"
            "Use this for local or private mail servers with self-signed certificates."
        )
        self._self_signed_cb.stateChanged.connect(self._save)
        form.addRow("", self._self_signed_cb)

        self._test_btn = QPushButton("Test Connection")
        self._test_btn.clicked.connect(self._on_test_connection)
        self._test_label = QLabel("")
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(self._test_btn)
        row_layout.addWidget(self._test_label)
        row_layout.addStretch()
        form.addRow("", row_widget)

        return box

    # ---- Appearance ----

    def _build_appearance_section(self) -> QGroupBox:
        box = QGroupBox("Appearance")
        form = QFormLayout(box)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["System default", "Light", "Dark"])
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        form.addRow("Theme:", self._theme_combo)

        return box

    # ------------------------------------------------------------------
    # Load config into UI
    # ------------------------------------------------------------------

    def _load_into_ui(self) -> None:
        cfg = self._config

        self._salutation_edit.setText(cfg.salutation)
        self._preamble_edit.setPlainText(cfg.preamble)
        self._closing_edit.setText(cfg.closing)
        self._signature_edit.setPlainText(cfg.signature)

        self._recv_edit.setText(cfg.default_receiver)
        self._ant_edit.setText(cfg.default_antenna)
        self._sw_edit.setText(cfg.default_software)
        self._os_edit.setText(cfg.default_os)

        for key, cb in self._field_checks.items():
            cb.setChecked(cfg.visible_fields.get(key, True))

        self._autofill_cb.setChecked(cfg.eibi_autofill)

        self._smtp_host.setText(cfg.smtp.host)
        self._smtp_port.setValue(cfg.smtp.port)
        self._smtp_user.setText(cfg.smtp.username)
        self._tls_cb.setChecked(cfg.smtp.use_tls)
        self._ssl_cb.setChecked(cfg.smtp.use_ssl)
        self._self_signed_cb.setChecked(cfg.smtp.accept_self_signed)

        # Load password from keyring (or file fallback)
        pwd = cfg_module.load_smtp_password(cfg)
        if pwd:
            self._smtp_pass.setText(pwd)

        idx = self._theme_combo.findText(cfg.theme)
        if idx >= 0:
            self._theme_combo.setCurrentIndex(idx)

        self._refresh_profile_list()

    # ------------------------------------------------------------------
    # Profiles
    # ------------------------------------------------------------------

    def _refresh_profile_list(self) -> None:
        self._profile_list.clear()
        profiles = log_store.get_all_profiles()
        for p in profiles:
            label = f"{'[ACTIVE] ' if p.is_active else ''}{p.name} <{p.email}>"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, p.id)
            self._profile_list.addItem(item)

    def _selected_profile_id(self) -> Optional[int]:
        item = self._profile_list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _on_add_profile(self) -> None:
        dlg = ProfileDialog(parent=self)
        if dlg.exec_() == dlg.Accepted:
            vals = dlg.values()
            p = SenderProfile(**vals)
            new_id = log_store.add_profile(p)
            profiles = log_store.get_all_profiles()
            if len(profiles) == 1:
                log_store.set_active_profile(new_id)
            self._refresh_profile_list()

    def _on_edit_profile(self) -> None:
        pid = self._selected_profile_id()
        if pid is None:
            return
        p = log_store.get_profile_by_id(pid)
        if p is None:
            return
        dlg = ProfileDialog(profile=p, parent=self)
        if dlg.exec_() == dlg.Accepted:
            vals = dlg.values()
            p.name = vals["name"]
            p.location = vals["location"]
            p.email = vals["email"]
            p.listener_number = vals["listener_number"]
            log_store.update_profile(p)
            self._refresh_profile_list()

    def _on_delete_profile(self) -> None:
        pid = self._selected_profile_id()
        if pid is None:
            return
        if QMessageBox.question(
            self, "Delete Profile",
            "Delete this sender profile? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        ) == QMessageBox.Yes:
            log_store.delete_profile(pid)
            self._refresh_profile_list()

    def _on_activate_profile(self) -> None:
        pid = self._selected_profile_id()
        if pid is None:
            return
        log_store.set_active_profile(pid)
        self._refresh_profile_list()

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _collect_config(self) -> AppConfig:
        cfg = self._config
        cfg.salutation = self._salutation_edit.text()
        cfg.preamble = self._preamble_edit.toPlainText()
        cfg.closing = self._closing_edit.text()
        cfg.signature = self._signature_edit.toPlainText()
        cfg.default_receiver = self._recv_edit.text()
        cfg.default_antenna = self._ant_edit.text()
        cfg.default_software = self._sw_edit.text()
        cfg.default_os = self._os_edit.text()
        for key, cb in self._field_checks.items():
            cfg.visible_fields[key] = cb.isChecked()
        cfg.eibi_autofill = self._autofill_cb.isChecked()
        cfg.smtp.host = self._smtp_host.text().strip()
        cfg.smtp.port = self._smtp_port.value()
        cfg.smtp.username = self._smtp_user.text().strip()
        cfg.smtp.use_tls = self._tls_cb.isChecked()
        cfg.smtp.use_ssl = self._ssl_cb.isChecked()
        cfg.smtp.accept_self_signed = self._self_signed_cb.isChecked()
        cfg.theme = self._theme_combo.currentText()
        return cfg

    def _save(self) -> None:
        if self._loading:
            return
        cfg = self._collect_config()
        cfg_module.save_config(cfg)
        self.config_changed.emit(cfg)

    def _on_field_visibility_changed(self) -> None:
        self._save()

    def _on_password_changed(self) -> None:
        pwd = self._smtp_pass.text()
        if not pwd:
            return

        if self._keyring_ok:
            if not cfg_module.save_smtp_password(pwd, use_fallback=False):
                QMessageBox.warning(
                    self, "Keyring Error",
                    "Could not save password to system keychain."
                )
        else:
            # Keyring unavailable — ask user for explicit consent before file save
            result = QMessageBox.question(
                self,
                "Store Password in Config File?",
                "Secure keychain storage is not available on this system.\n\n"
                "Do you want to store the SMTP password in the config file instead?\n"
                "The file is readable by anyone with access to your user profile.",
                QMessageBox.Yes | QMessageBox.No,
            )
            if result == QMessageBox.Yes:
                self._config.password_fallback = True
                cfg_module.save_smtp_password(pwd, use_fallback=True)
                cfg_module.save_config(self._config)
            else:
                self._smtp_pass.clear()

        self._save()

    # ------------------------------------------------------------------
    # SMTP test
    # ------------------------------------------------------------------

    def _on_test_connection(self) -> None:
        if self._test_worker and self._test_worker.isRunning():
            return

        cfg = self._collect_config()
        pwd = self._smtp_pass.text()

        if not cfg.smtp.host:
            QMessageBox.warning(self, "SMTP Not Configured", "Please enter an SMTP host.")
            return

        self._test_btn.setEnabled(False)
        self._test_label.setText("Testing…")

        self._test_worker = TestConnectionWorker(
            smtp_cfg=cfg.smtp, password=pwd, parent=self
        )
        self._test_worker.success.connect(self._on_test_success)
        self._test_worker.error.connect(self._on_test_error)
        self._test_worker.start()

    def _on_test_success(self) -> None:
        self._test_btn.setEnabled(True)
        self._test_label.setText("Connection OK")
        self._test_label.setStyleSheet("color: green;")

    def _on_test_error(self, message: str) -> None:
        self._test_btn.setEnabled(True)
        self._test_label.setText("Failed")
        self._test_label.setStyleSheet("color: red;")
        QMessageBox.critical(self, "Connection Test Failed", message)

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _on_theme_changed(self) -> None:
        self._save()
        theme = self._theme_combo.currentText()
        self._apply_theme(theme)

    def _apply_theme(self, theme: str) -> None:
        from ui.theme import apply_theme
        apply_theme(theme)

    def refresh_config(self, app_config: AppConfig) -> None:
        self._config = app_config
        self._load_into_ui()
