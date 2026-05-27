from dataclasses import dataclass, field
from typing import Dict


DEFAULT_VISIBLE_FIELDS: Dict[str, bool] = {
    "language": True,
    "target_region": True,
    "transmitter_site": True,
    "receiver": True,
    "antenna": True,
    "software": True,
    "operating_system": True,
    "qsl_preference": True,
    "listener_number": True,
    "fading": True,
    "interference": True,
    "programme_details": True,
    "remarks": True,
}

OPTIONAL_FIELD_LABELS: Dict[str, str] = {
    "language": "Language",
    "target_region": "Target Region",
    "transmitter_site": "Transmitter Site / Relay",
    "receiver": "Receiver",
    "antenna": "Antenna",
    "software": "Software Used",
    "operating_system": "Operating System",
    "qsl_preference": "QSL Preference",
    "listener_number": "Listener / Membership Number",
    "fading": "Signal Fading Observations",
    "interference": "Interference Sources",
    "programme_details": "Programme Details Heard",
    "remarks": "Remarks",
}


@dataclass
class SenderProfile:
    id: int = 0
    name: str = ""
    location: str = ""
    email: str = ""
    listener_number: str = ""
    is_active: bool = False


@dataclass
class SMTPConfig:
    host: str = ""
    port: int = 587
    username: str = ""
    use_tls: bool = True
    use_ssl: bool = False


@dataclass
class ReportEntry:
    id: int = 0
    station_name: str = ""
    frequency: float = 0.0
    mode: str = "AM"
    date_utc: str = ""
    time_utc: str = ""
    sinpo: str = ""
    recipient_email: str = ""
    status: str = "Draft"
    language: str = ""
    target_region: str = ""
    transmitter_site: str = ""
    receiver: str = ""
    antenna: str = ""
    software: str = ""
    operating_system: str = ""
    qsl_preference: str = ""
    listener_number: str = ""
    fading: str = ""
    interference: str = ""
    programme_details: str = ""
    remarks: str = ""
    created_at: str = ""
    sender_profile_id: int = 0


@dataclass
class EIBIStation:
    id: int = 0
    station_name: str = ""
    frequency: float = 0.0
    language: str = ""
    target_region: str = ""
    transmitter_site: str = ""
    days: str = ""
    start_time_utc: str = ""
    end_time_utc: str = ""
    is_user_added: bool = False


@dataclass
class AppConfig:
    salutation: str = "Dear Sir or Madam,"
    preamble: str = (
        "I would like to submit the following reception report and kindly "
        "request a QSL confirmation if possible."
    )
    closing: str = "Thank you for your broadcasts."
    signature: str = ""
    default_receiver: str = ""
    default_antenna: str = ""
    default_software: str = ""
    default_os: str = ""
    visible_fields: Dict[str, bool] = field(
        default_factory=lambda: dict(DEFAULT_VISIBLE_FIELDS)
    )
    eibi_autofill: bool = True
    theme: str = "System default"
    active_profile_id: int = 0
    smtp: SMTPConfig = field(default_factory=SMTPConfig)
    # True when the user has explicitly consented to file-based password storage
    # because keyring is unavailable on their system.
    password_fallback: bool = False
