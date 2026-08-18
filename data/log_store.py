"""
CRUD operations for reception reports and sender profiles.
"""

import sqlite3
from datetime import datetime, timezone
from typing import List, Optional

from models import ReportEntry, SenderProfile
from data.database import get_connection


# ---------------------------------------------------------------------------
# Sender profiles
# ---------------------------------------------------------------------------

def _profile_from_row(row: sqlite3.Row) -> SenderProfile:
    keys = row.keys()
    return SenderProfile(
        id=row["id"],
        name=row["name"],
        location=row["location"],
        email=row["email"],
        listener_number=row["listener_number"],
        is_active=bool(row["is_active"]),
        postal_address=row["postal_address"] if "postal_address" in keys else "",
    )


def get_all_profiles() -> List[SenderProfile]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM sender_profiles ORDER BY id"
    ).fetchall()
    return [_profile_from_row(r) for r in rows]


def get_active_profile() -> Optional[SenderProfile]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM sender_profiles WHERE is_active = 1 LIMIT 1"
    ).fetchone()
    return _profile_from_row(row) if row else None


def get_profile_by_id(profile_id: int) -> Optional[SenderProfile]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM sender_profiles WHERE id = ?", (profile_id,)
    ).fetchone()
    return _profile_from_row(row) if row else None


def add_profile(profile: SenderProfile) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO sender_profiles "
        "(name, location, email, listener_number, is_active, postal_address) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            profile.name,
            profile.location,
            profile.email,
            profile.listener_number,
            int(profile.is_active),
            profile.postal_address,
        ),
    )
    conn.commit()
    return cur.lastrowid


def update_profile(profile: SenderProfile) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE sender_profiles SET name=?, location=?, email=?, "
        "listener_number=?, is_active=?, postal_address=? WHERE id=?",
        (
            profile.name,
            profile.location,
            profile.email,
            profile.listener_number,
            int(profile.is_active),
            profile.postal_address,
            profile.id,
        ),
    )
    conn.commit()


def delete_profile(profile_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM sender_profiles WHERE id = ?", (profile_id,))
    conn.commit()


def set_active_profile(profile_id: int) -> None:
    """Set exactly one profile active; all others become inactive."""
    conn = get_connection()
    conn.execute("UPDATE sender_profiles SET is_active = 0")
    conn.execute(
        "UPDATE sender_profiles SET is_active = 1 WHERE id = ?", (profile_id,)
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def get_next_report_number() -> int:
    """Return the next sequential report number (MAX + 1 across all saved reports)."""
    conn = get_connection()
    row = conn.execute(
        "SELECT COALESCE(MAX(report_number), 0) + 1 FROM reports"
    ).fetchone()
    return row[0]


def _report_from_row(row: sqlite3.Row) -> ReportEntry:
    keys = row.keys()
    return ReportEntry(
        id=row["id"],
        report_number=row["report_number"] if "report_number" in keys else 0,
        station_name=row["station_name"],
        frequency=float(row["frequency"]),
        mode=row["mode"],
        date_utc=row["date_utc"],
        time_utc=row["time_utc"],
        sinpo=row["sinpo"],
        recipient_email=row["recipient_email"],
        status=row["status"],
        language=row["language"],
        target_region=row["target_region"],
        transmitter_site=row["transmitter_site"],
        receiver=row["receiver"],
        antenna=row["antenna"],
        software=row["software"],
        operating_system=row["operating_system"],
        qsl_preference=row["qsl_preference"],
        listener_number=row["listener_number"],
        fading=row["fading"],
        interference=row["interference"],
        programme_details=row["programme_details"],
        remarks=row["remarks"],
        station_address=row["station_address"] if "station_address" in keys else "",
        created_at=row["created_at"],
        sender_profile_id=row["sender_profile_id"],
    )


def get_all_reports() -> List[ReportEntry]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM reports ORDER BY date_utc DESC, time_utc DESC"
    ).fetchall()
    return [_report_from_row(r) for r in rows]


def get_report_by_id(report_id: int) -> Optional[ReportEntry]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM reports WHERE id = ?", (report_id,)
    ).fetchone()
    return _report_from_row(row) if row else None


def save_report(entry: ReportEntry) -> int:
    """Insert a new report and return its id."""
    conn = get_connection()
    now_utc = datetime.now(timezone.utc).isoformat()
    if entry.report_number == 0:
        row = conn.execute(
            "SELECT COALESCE(MAX(report_number), 0) + 1 FROM reports"
        ).fetchone()
        entry.report_number = row[0]
    cur = conn.execute(
        """INSERT INTO reports (
            station_name, frequency, mode, date_utc, time_utc, sinpo,
            recipient_email, status, language, target_region, transmitter_site,
            receiver, antenna, software, operating_system, qsl_preference,
            listener_number, fading, interference, programme_details, remarks,
            station_address, created_at, sender_profile_id, report_number
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            entry.station_name, entry.frequency, entry.mode,
            entry.date_utc, entry.time_utc, entry.sinpo,
            entry.recipient_email, entry.status,
            entry.language, entry.target_region, entry.transmitter_site,
            entry.receiver, entry.antenna, entry.software, entry.operating_system,
            entry.qsl_preference, entry.listener_number,
            entry.fading, entry.interference, entry.programme_details, entry.remarks,
            entry.station_address,
            now_utc, entry.sender_profile_id, entry.report_number,
        ),
    )
    conn.commit()
    return cur.lastrowid


def update_report(entry: ReportEntry) -> None:
    conn = get_connection()
    conn.execute(
        """UPDATE reports SET
            station_name=?, frequency=?, mode=?, date_utc=?, time_utc=?, sinpo=?,
            recipient_email=?, status=?, language=?, target_region=?, transmitter_site=?,
            receiver=?, antenna=?, software=?, operating_system=?, qsl_preference=?,
            listener_number=?, fading=?, interference=?, programme_details=?, remarks=?,
            station_address=?, sender_profile_id=?
        WHERE id=?""",
        (
            entry.station_name, entry.frequency, entry.mode,
            entry.date_utc, entry.time_utc, entry.sinpo,
            entry.recipient_email, entry.status,
            entry.language, entry.target_region, entry.transmitter_site,
            entry.receiver, entry.antenna, entry.software, entry.operating_system,
            entry.qsl_preference, entry.listener_number,
            entry.fading, entry.interference, entry.programme_details, entry.remarks,
            entry.station_address, entry.sender_profile_id, entry.id,
        ),
    )
    conn.commit()


def update_report_status(report_id: int, status: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE reports SET status = ? WHERE id = ?", (status, report_id)
    )
    conn.commit()


def delete_report(report_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
    conn.commit()


def get_known_station_names() -> List[str]:
    """Return all station names that appear in saved reports (for autocomplete)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT station_name FROM reports ORDER BY station_name"
    ).fetchall()
    return [r["station_name"] for r in rows]
