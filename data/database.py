"""
SQLite database initialisation and low-level access for EtherLog.

Each call that touches the database creates or reuses a per-thread connection
via threading.local() so that SQLite's thread-isolation guarantees are
respected without having to serialize every query through a single mutex.
"""

import sqlite3
import threading
import logging
from pathlib import Path
from datetime import datetime, timezone

log = logging.getLogger(__name__)

_local = threading.local()
_db_path: Path | None = None


def init_db(db_path: Path) -> None:
    """Store the database path and create all tables on first use."""
    global _db_path
    _db_path = db_path
    _ensure_schema(_get_conn())


def _get_conn() -> sqlite3.Connection:
    """Return a thread-local SQLite connection, creating one if needed."""
    if _db_path is None:
        raise RuntimeError("Database has not been initialised; call init_db() first.")
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(_db_path))
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA foreign_keys = ON")
        _local.conn.execute("PRAGMA journal_mode = WAL")
    return _local.conn


def get_connection() -> sqlite3.Connection:
    """Public accessor used by other data modules."""
    return _get_conn()


# ---------------------------------------------------------------------------
# Schema creation & migrations
# ---------------------------------------------------------------------------

def _ensure_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS sender_profiles (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT    NOT NULL,
            location        TEXT    NOT NULL DEFAULT '',
            email           TEXT    NOT NULL DEFAULT '',
            listener_number TEXT    NOT NULL DEFAULT '',
            is_active       INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS reports (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            station_name      TEXT    NOT NULL,
            frequency         REAL    NOT NULL DEFAULT 0,
            mode              TEXT    NOT NULL DEFAULT 'AM',
            date_utc          TEXT    NOT NULL DEFAULT '',
            time_utc          TEXT    NOT NULL DEFAULT '',
            sinpo             TEXT    NOT NULL DEFAULT '',
            recipient_email   TEXT    NOT NULL DEFAULT '',
            status            TEXT    NOT NULL DEFAULT 'Draft',
            language          TEXT    NOT NULL DEFAULT '',
            target_region     TEXT    NOT NULL DEFAULT '',
            transmitter_site  TEXT    NOT NULL DEFAULT '',
            receiver          TEXT    NOT NULL DEFAULT '',
            antenna           TEXT    NOT NULL DEFAULT '',
            software          TEXT    NOT NULL DEFAULT '',
            operating_system  TEXT    NOT NULL DEFAULT '',
            qsl_preference    TEXT    NOT NULL DEFAULT '',
            listener_number   TEXT    NOT NULL DEFAULT '',
            fading            TEXT    NOT NULL DEFAULT '',
            interference      TEXT    NOT NULL DEFAULT '',
            programme_details TEXT    NOT NULL DEFAULT '',
            remarks           TEXT    NOT NULL DEFAULT '',
            created_at        TEXT    NOT NULL DEFAULT '',
            sender_profile_id INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS eibi_stations (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            station_name     TEXT    NOT NULL,
            frequency        REAL    NOT NULL DEFAULT 0,
            language         TEXT    NOT NULL DEFAULT '',
            target_region    TEXT    NOT NULL DEFAULT '',
            transmitter_site TEXT    NOT NULL DEFAULT '',
            days             TEXT    NOT NULL DEFAULT '',
            start_time_utc   TEXT    NOT NULL DEFAULT '',
            end_time_utc     TEXT    NOT NULL DEFAULT '',
            is_user_added    INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS meta (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        );
    """)
    conn.commit()

    # Migrate: add any columns introduced after initial release
    _add_column_if_missing(conn, "reports", "operating_system", "TEXT NOT NULL DEFAULT ''")


def _add_column_if_missing(
    conn: sqlite3.Connection, table: str, column: str, definition: str
) -> None:
    """Idempotent column addition used for lightweight schema migrations."""
    cur = conn.execute(f"PRAGMA table_info({table})")
    existing = {row["name"] for row in cur.fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        conn.commit()
        log.info("Migration: added column %s.%s", table, column)


# ---------------------------------------------------------------------------
# Meta helpers (last EIBI update date, etc.)
# ---------------------------------------------------------------------------

def get_meta(key: str, default: str = "") -> str:
    conn = _get_conn()
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(key: str, value: str) -> None:
    conn = _get_conn()
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()
