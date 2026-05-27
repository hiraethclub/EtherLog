"""
SMTP email sending for EtherLog.

All network operations run in QThread workers so the UI never blocks.
Signals carry success/failure back to the main thread for display.
"""

from __future__ import annotations

import smtplib
import ssl
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from PyQt5.QtCore import QThread, pyqtSignal

from models import SMTPConfig

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Plain send helper (runs inside a worker thread)
# ---------------------------------------------------------------------------

def send_email(
    smtp_cfg: SMTPConfig,
    password: str,
    from_addr: str,
    to_addr: str,
    subject: str,
    body: str,
) -> None:
    """
    Synchronously send one email.  Raises smtplib exceptions on failure.
    Caller is responsible for running this in a thread.
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.attach(MIMEText(body, "plain", "utf-8"))

    host = smtp_cfg.host
    port = smtp_cfg.port

    def _make_ssl_ctx() -> ssl.SSLContext:
        ctx = ssl.create_default_context()
        if smtp_cfg.accept_self_signed:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        return ctx

    if smtp_cfg.use_ssl:
        with smtplib.SMTP_SSL(host, port, context=_make_ssl_ctx(), timeout=30) as server:
            if password:
                server.login(smtp_cfg.username, password)
            server.sendmail(from_addr, [to_addr], msg.as_string())
    else:
        with smtplib.SMTP(host, port, timeout=30) as server:
            if smtp_cfg.use_tls:
                server.starttls(context=_make_ssl_ctx())
            if password:
                server.login(smtp_cfg.username, password)
            server.sendmail(from_addr, [to_addr], msg.as_string())


def test_connection(smtp_cfg: SMTPConfig, password: str) -> None:
    """
    Open and immediately close an SMTP connection to verify credentials.
    Raises smtplib exceptions on failure.
    """
    host = smtp_cfg.host
    port = smtp_cfg.port

    def _make_ssl_ctx() -> ssl.SSLContext:
        ctx = ssl.create_default_context()
        if smtp_cfg.accept_self_signed:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        return ctx

    if smtp_cfg.use_ssl:
        with smtplib.SMTP_SSL(host, port, context=_make_ssl_ctx(), timeout=15) as server:
            if password:
                server.login(smtp_cfg.username, password)
    else:
        with smtplib.SMTP(host, port, timeout=15) as server:
            if smtp_cfg.use_tls:
                server.starttls(context=_make_ssl_ctx())
            if password:
                server.login(smtp_cfg.username, password)


# ---------------------------------------------------------------------------
# QThread workers
# ---------------------------------------------------------------------------

class SendEmailWorker(QThread):
    """Worker thread for sending a single email report."""

    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(
        self,
        smtp_cfg: SMTPConfig,
        password: str,
        from_addr: str,
        to_addr: str,
        subject: str,
        body: str,
        parent=None,
    ):
        super().__init__(parent)
        self._smtp_cfg = smtp_cfg
        self._password = password
        self._from = from_addr
        self._to = to_addr
        self._subject = subject
        self._body = body

    def run(self) -> None:
        try:
            send_email(
                self._smtp_cfg,
                self._password,
                self._from,
                self._to,
                self._subject,
                self._body,
            )
            self.finished.emit()
        except smtplib.SMTPAuthenticationError:
            self.error.emit(
                "Authentication failed. Please check your SMTP username and password."
            )
        except smtplib.SMTPConnectError as exc:
            self.error.emit(
                f"Could not connect to {self._smtp_cfg.host}:{self._smtp_cfg.port}.\n"
                f"Check the host and port in Configuration.\n\nDetail: {exc.smtp_error!s}"
            )
        except smtplib.SMTPRecipientsRefused:
            self.error.emit(
                f"The recipient address '{self._to}' was rejected by the server."
            )
        except smtplib.SMTPException as exc:
            self.error.emit(f"SMTP error: {exc}")
        except OSError as exc:
            self.error.emit(
                f"Network error while sending email.\n\nDetail: {exc}"
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("Unexpected send error")
            self.error.emit(f"Unexpected error: {exc}")


class TestConnectionWorker(QThread):
    """Worker thread for testing SMTP connectivity."""

    success = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, smtp_cfg: SMTPConfig, password: str, parent=None):
        super().__init__(parent)
        self._smtp_cfg = smtp_cfg
        self._password = password

    def run(self) -> None:
        try:
            test_connection(self._smtp_cfg, self._password)
            self.success.emit()
        except smtplib.SMTPAuthenticationError:
            self.error.emit(
                "Authentication failed. Check your SMTP username and password."
            )
        except smtplib.SMTPConnectError as exc:
            self.error.emit(
                f"Could not connect to {self._smtp_cfg.host}:{self._smtp_cfg.port}.\n"
                f"Detail: {exc.smtp_error!s}"
            )
        except smtplib.SMTPException as exc:
            self.error.emit(f"SMTP error: {exc}")
        except OSError as exc:
            self.error.emit(f"Network error: {exc}")
        except Exception as exc:  # noqa: BLE001
            log.exception("Unexpected test-connection error")
            self.error.emit(f"Unexpected error: {exc}")
