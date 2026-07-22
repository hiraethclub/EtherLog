"""
Configuration management for EtherLog.

Config and database files live next to the application itself so the whole
folder can be moved or copied to any machine or USB drive without losing data
(portable-app behaviour).

SMTP password is kept out of the JSON file and stored via the system keychain
using the `keyring` library.  If keyring is unavailable the module falls back
to file storage only after explicit user consent.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

# keyring is an optional dependency.  If it is not installed the app still
# starts and falls back to file-based password storage with user consent.
try:
    import keyring
    _KEYRING_IMPORTABLE = True
except ImportError:
    keyring = None  # type: ignore[assignment]
    _KEYRING_IMPORTABLE = False

from models import AppConfig, SMTPConfig, SenderProfile

log = logging.getLogger(__name__)

_KEYRING_SERVICE = "EtherLog-SMTP"
_KEYRING_USERNAME = "smtp_password"


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _get_app_dir() -> Path:
    """
    Return the directory that contains the application.

    When frozen by PyInstaller the data directory is the folder that contains
    the executable (.exe / binary), so the app is fully self-contained and
    portable.  When running from source it is the directory that contains
    this file (the project root).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_config_dir() -> Path:
    """Return (and create if needed) the directory used for config and data files.

    Both config.json and etherlog.db are stored here, next to the program,
    so the entire folder can be moved or copied without losing any data.
    """
    d = _get_app_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_config_path() -> Path:
    return get_config_dir() / "config.json"


def get_db_path() -> Path:
    return get_config_dir() / "etherlog.db"


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _smtp_to_dict(smtp: SMTPConfig) -> dict:
    return {
        "host": smtp.host,
        "port": smtp.port,
        "username": smtp.username,
        "use_tls": smtp.use_tls,
        "use_ssl": smtp.use_ssl,
        "accept_self_signed": smtp.accept_self_signed,
    }


def _smtp_from_dict(d: dict) -> SMTPConfig:
    return SMTPConfig(
        host=d.get("host", ""),
        port=int(d.get("port", 587)),
        username=d.get("username", ""),
        use_tls=bool(d.get("use_tls", True)),
        use_ssl=bool(d.get("use_ssl", False)),
        accept_self_signed=bool(d.get("accept_self_signed", False)),
    )


def _profile_to_dict(p: SenderProfile) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "location": p.location,
        "email": p.email,
        "listener_number": p.listener_number,
        "is_active": p.is_active,
        "postal_address": p.postal_address,
    }


def _profile_from_dict(d: dict) -> SenderProfile:
    return SenderProfile(
        id=int(d.get("id", 0)),
        name=d.get("name", ""),
        location=d.get("location", ""),
        email=d.get("email", ""),
        listener_number=d.get("listener_number", ""),
        is_active=bool(d.get("is_active", False)),
        postal_address=d.get("postal_address", ""),
    )


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def load_config() -> AppConfig:
    path = get_config_path()
    if not path.exists():
        return AppConfig()

    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        log.warning("Could not load config (%s); using defaults.", exc)
        return AppConfig()

    cfg = AppConfig()
    cfg.salutation = data.get("salutation", cfg.salutation)
    cfg.preamble = data.get("preamble", cfg.preamble)
    cfg.closing = data.get("closing", cfg.closing)
    cfg.signature = data.get("signature", cfg.signature)
    cfg.default_receiver = data.get("default_receiver", "")
    cfg.default_antenna = data.get("default_antenna", "")
    cfg.default_software = data.get("default_software", "")
    cfg.default_os = data.get("default_os", "")
    cfg.eibi_autofill = bool(data.get("eibi_autofill", True))
    cfg.theme = data.get("theme", "System default")
    cfg.active_profile_id = int(data.get("active_profile_id", 0))
    cfg.password_fallback = bool(data.get("password_fallback", False))

    if "visible_fields" in data:
        cfg.visible_fields.update(data["visible_fields"])

    if "smtp" in data:
        cfg.smtp = _smtp_from_dict(data["smtp"])

    return cfg


def save_config(cfg: AppConfig) -> None:
    path = get_config_path()
    data = {
        "salutation": cfg.salutation,
        "preamble": cfg.preamble,
        "closing": cfg.closing,
        "signature": cfg.signature,
        "default_receiver": cfg.default_receiver,
        "default_antenna": cfg.default_antenna,
        "default_software": cfg.default_software,
        "default_os": cfg.default_os,
        "visible_fields": cfg.visible_fields,
        "eibi_autofill": cfg.eibi_autofill,
        "theme": cfg.theme,
        "active_profile_id": cfg.active_profile_id,
        "password_fallback": cfg.password_fallback,
        "smtp": _smtp_to_dict(cfg.smtp),
    }
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    except Exception as exc:
        log.error("Could not save config: %s", exc)


# ---------------------------------------------------------------------------
# Keyring helpers
# ---------------------------------------------------------------------------

def load_smtp_password(fallback_cfg: Optional[AppConfig] = None) -> str:
    """Return the SMTP password from keyring, or from config file fallback."""
    if _KEYRING_IMPORTABLE:
        try:
            pwd = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USERNAME)
            return pwd or ""
        except BaseException as exc:
            # Catch BaseException: some backends (SecretService via pyo3) raise
            # PanicException which does not inherit from Exception.
            log.warning("keyring unavailable (%s); trying file fallback.", exc)

    # File fallback: password stored directly in config JSON
    if fallback_cfg is not None and fallback_cfg.password_fallback:
        path = get_config_path()
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data.get("smtp_password_fallback", "")
        except Exception:
            pass
    return ""


def save_smtp_password(password: str, use_fallback: bool = False) -> bool:
    """
    Save the SMTP password.  Returns True on success.
    If keyring fails and use_fallback is True, writes to the config JSON instead
    (only after the user has explicitly consented – the caller is responsible
    for setting use_fallback=True only after confirmation).
    """
    if _KEYRING_IMPORTABLE:
        try:
            keyring.set_password(_KEYRING_SERVICE, _KEYRING_USERNAME, password)
            return True
        except BaseException as exc:
            log.warning("keyring save failed (%s).", exc)

    if use_fallback:
        path = get_config_path()
        try:
            data: dict = {}
            if path.exists():
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            data["smtp_password_fallback"] = password
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
            return True
        except Exception as exc2:
            log.error("file fallback password save failed: %s", exc2)
    return False


def keyring_available() -> bool:
    """
    Quick probe: is keyring installed AND able to round-trip a value?
    Returns False if keyring is not installed or the backend is broken.
    """
    if not _KEYRING_IMPORTABLE:
        return False
    try:
        keyring.set_password(_KEYRING_SERVICE, "__probe__", "1")
        keyring.delete_password(_KEYRING_SERVICE, "__probe__")
        return True
    except BaseException:
        # BaseException (not just Exception) is required: some backends raise
        # pyo3_runtime.PanicException when native libraries are missing.
        return False


def is_first_run() -> bool:
    """True when no config file exists (genuine first launch)."""
    return not get_config_path().exists()
