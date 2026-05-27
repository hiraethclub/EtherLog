"""
Email send dialog for EtherLog.

Shown when the user clicks "Send via Email" in the New Report tab.
Provides editable recipient address, subject, full body preview, and a Send
button that dispatches via a QThread worker.
"""

from __future__ import annotations

from typing import Optional

from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget,
    QHBoxLayout,
)
from PyQt5.QtCore import Qt

from email_handler import SendEmailWorker
from models import AppConfig, SMTPConfig
import config as cfg_module


class SendDialog(QDialog):
    def __init__(
        self,
        subject: str,
        body: str,
        app_config: AppConfig,
        from_addr: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Send Report via Email")
        self.resize(600, 500)

        self._app_config = app_config
        self._from_addr = from_addr
        self._worker: Optional[SendEmailWorker] = None

        layout = QVBoxLayout(self)

        form = QFormLayout()
        layout.addLayout(form)

        self._to_edit = QLineEdit()
        form.addRow("Recipient:", self._to_edit)

        self._subject_edit = QLineEdit(subject)
        form.addRow("Subject:", self._subject_edit)

        layout.addWidget(QLabel("Email body preview (editable):"))

        self._body_edit = QTextEdit()
        self._body_edit.setPlainText(body)
        self._body_edit.setMinimumHeight(280)
        layout.addWidget(self._body_edit)

        btn_row = QHBoxLayout()
        layout.addLayout(btn_row)

        self._send_btn = QPushButton("Send")
        self._send_btn.setDefault(True)
        self._send_btn.clicked.connect(self._on_send)
        btn_row.addStretch()
        btn_row.addWidget(self._send_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

    def _on_send(self) -> None:
        to_addr = self._to_edit.text().strip()
        if not to_addr:
            QMessageBox.warning(self, "Missing Recipient", "Please enter a recipient email address.")
            return

        smtp = self._app_config.smtp
        if not smtp.host:
            QMessageBox.warning(
                self,
                "SMTP Not Configured",
                "No SMTP server is configured. Please set up SMTP in the Configuration tab.",
            )
            return

        password = cfg_module.load_smtp_password(self._app_config)

        self._send_btn.setEnabled(False)
        self._status_label.setText("Sending…")

        self._worker = SendEmailWorker(
            smtp_cfg=smtp,
            password=password,
            from_addr=self._from_addr,
            to_addr=to_addr,
            subject=self._subject_edit.text(),
            body=self._body_edit.toPlainText(),
            parent=self,
        )
        self._worker.finished.connect(self._on_success)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_success(self) -> None:
        self._status_label.setText("Sent successfully.")
        self._send_btn.setEnabled(True)
        # Store recipient so the caller can update the log
        self.accepted_to = self._to_edit.text().strip()
        self.accept()

    def _on_error(self, message: str) -> None:
        self._send_btn.setEnabled(True)
        self._status_label.setText("Send failed.")
        QMessageBox.critical(self, "Send Failed", message)

    def get_recipient(self) -> str:
        return self._to_edit.text().strip()
