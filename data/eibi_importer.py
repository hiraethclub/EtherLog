"""
EIBI shortwave schedule database download and import.

The EIBI schedule lives at http://www.eibispace.de.  Filenames follow the
pattern sked-X##.csv where X is A (spring/summer, Mar–Oct) or B
(autumn/winter, Nov–Feb) and ## is the two-digit year.

Strategy:
  1. Fetch the EIBI index page and parse it for a link matching the pattern.
  2. If parsing fails, construct the expected filename from the current UTC date.
  3. Download the CSV with latin-1 encoding (the file is not UTF-8).
  4. Bulk-import into SQLite, preserving any rows with is_user_added = 1.

All work runs inside a QThread worker; signals report progress and completion.
"""

from __future__ import annotations

import csv
import io
import logging
import re
import sqlite3
from datetime import datetime, timezone
from typing import Optional

import urllib.request
import urllib.error

from PyQt5.QtCore import QThread, pyqtSignal

from data.database import get_connection, set_meta

log = logging.getLogger(__name__)

EIBI_BASE_URL = "http://www.eibispace.de"


# ---------------------------------------------------------------------------
# Season / filename helpers
# ---------------------------------------------------------------------------

def _current_season_filename() -> str:
    """
    Derive the most likely current EIBI CSV filename from today's UTC date.

    Season A (spring/summer) runs from the last Sunday of March to the last
    Saturday of October.  Season B covers the rest of the year.  For simplicity
    we use month boundaries: A = March–October, B = November–February.
    """
    now = datetime.now(timezone.utc)
    year_2digit = now.strftime("%y")
    # Approximate boundary: month 3–10 → A season, otherwise B
    season = "a" if 3 <= now.month <= 10 else "b"
    return f"sked-{season}{year_2digit}.csv"


def _parse_index_for_csv_link(html: str) -> Optional[str]:
    """
    Extract the href of the first .csv link on the EIBI index page.
    Returns just the filename (e.g. 'sked-a25.csv'), or None if not found.
    """
    # Look for href="sked-X##.csv" (case-insensitive)
    pattern = re.compile(r'href="(sked-[abAB]\d{2}\.csv)"', re.IGNORECASE)
    match = pattern.search(html)
    if match:
        return match.group(1)
    return None


def _download_text(url: str, encoding: str = "utf-8") -> str:
    """Fetch a URL and return the body decoded with the given encoding."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "EtherLog/1.0 (shortwave reception logger)"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    return raw.decode(encoding, errors="replace")


def resolve_eibi_csv_url() -> str:
    """
    Return the full URL of the current EIBI season CSV.
    Tries to parse the index page first; falls back to a constructed filename.
    """
    try:
        html = _download_text(EIBI_BASE_URL)
        filename = _parse_index_for_csv_link(html)
        if filename:
            log.info("EIBI: found CSV link on index page: %s", filename)
            return f"{EIBI_BASE_URL}/{filename}"
    except Exception as exc:
        log.warning("EIBI: index page parse failed (%s); using constructed filename.", exc)

    # Fallback: construct filename from current UTC date
    filename = _current_season_filename()
    log.info("EIBI: using constructed filename: %s", filename)
    return f"{EIBI_BASE_URL}/{filename}"


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------

def parse_eibi_csv(csv_text: str) -> list[dict]:
    """
    Parse EIBI CSV into a list of dicts.

    Standard EIBI format (latin-1, semicolon-delimited, 14 columns):
      kHz;ITU;Start;Stop;Days;Country;Target;Language;TxSite;Remarks;P;StartDate;StopDate;Programme

    The broadcaster/station name is the last column, labelled 'Programme' in the
    header (not 'Station' or 'Name').  Column count can vary between seasons, so
    we also handle headerless files with a positional fallback.
    """
    rows = []
    reader = csv.reader(io.StringIO(csv_text), delimiter=";")

    header = None
    for raw_row in reader:
        if not raw_row or raw_row[0].startswith("#"):
            continue

        # Detect header row: first cell is 'kHz' or 'Freq'
        if raw_row[0].strip().lower() in ("khz", "freq", "frequency"):
            header = [c.strip().lower() for c in raw_row]
            continue

        if len(raw_row) < 5:
            continue

        try:
            if header:
                def col(name: str, default: str = "") -> str:
                    try:
                        return raw_row[header.index(name)].strip()
                    except (ValueError, IndexError):
                        return default

                freq_str = col("khz") or col("freq") or col("frequency")
                start = col("start") or col("utcstart")
                stop = col("stop") or col("end") or col("utcend")
                days = col("days")
                language = col("language") or col("lang")
                target = col("target") or col("area")
                txsite = col("txsite") or col("site")
                # EIBI uses 'Programme' for the broadcaster name, not 'Station'
                station = (
                    col("programme")
                    or col("broadcaster")
                    or col("station")
                    or col("name")
                )
            else:
                # Positional fallback for the standard 14-column EIBI format:
                #   0=kHz  1=ITU  2=Start  3=Stop  4=Days  5=Country  6=Target
                #   7=Language  8=TxSite  9=Remarks  10=P  11=StartDate
                #   12=StopDate  13=Programme (broadcaster/station name)
                freq_str = raw_row[0].strip()
                start = raw_row[2].strip() if len(raw_row) > 2 else ""
                stop = raw_row[3].strip() if len(raw_row) > 3 else ""
                days = raw_row[4].strip() if len(raw_row) > 4 else ""
                target = raw_row[6].strip() if len(raw_row) > 6 else ""
                language = raw_row[7].strip() if len(raw_row) > 7 else ""
                txsite = raw_row[8].strip() if len(raw_row) > 8 else ""
                # Station name at index 13 (14-col format) or last column otherwise
                if len(raw_row) > 13:
                    station = raw_row[13].strip()
                elif len(raw_row) > 9:
                    station = raw_row[-1].strip()
                else:
                    station = ""

            try:
                freq = float(freq_str)
            except ValueError:
                continue

            if not station:
                continue

            rows.append({
                "station_name": station,
                "frequency": freq,
                "language": language,
                "target_region": target,
                "transmitter_site": txsite,
                "days": days,
                "start_time_utc": start,
                "end_time_utc": stop,
            })
        except Exception as exc:  # noqa: BLE001
            log.debug("EIBI: skipped row (%s): %s", exc, raw_row)
            continue

    return rows


def import_eibi_rows(rows: list[dict]) -> int:
    """
    Bulk-replace EIBI station data in SQLite.
    User-added stations (is_user_added = 1) are never touched.
    Returns the number of rows imported.
    """
    conn = get_connection()

    # Delete all non-user-added stations
    conn.execute("DELETE FROM eibi_stations WHERE is_user_added = 0")

    if not rows:
        conn.commit()
        return 0

    conn.executemany(
        """INSERT INTO eibi_stations
           (station_name, frequency, language, target_region,
            transmitter_site, days, start_time_utc, end_time_utc, is_user_added)
           VALUES (:station_name, :frequency, :language, :target_region,
                   :transmitter_site, :days, :start_time_utc, :end_time_utc, 0)""",
        rows,
    )
    conn.commit()

    # Record the import timestamp
    set_meta("eibi_last_updated", datetime.now(timezone.utc).isoformat())
    return len(rows)


# ---------------------------------------------------------------------------
# Station query helpers
# ---------------------------------------------------------------------------

def get_all_eibi_stations() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM eibi_stations ORDER BY station_name"
    ).fetchall()
    return [dict(r) for r in rows]


def get_eibi_station_names() -> list[str]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT station_name FROM eibi_stations ORDER BY station_name"
    ).fetchall()
    return [r["station_name"] for r in rows]


def get_eibi_data_for_station(name: str) -> Optional[dict]:
    """
    Return the first matching EIBI row for a station name (for autofill).
    Returns None if not found.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM eibi_stations WHERE station_name = ? LIMIT 1", (name,)
    ).fetchone()
    return dict(row) if row else None


def add_user_station(
    station_name: str,
    frequency: float,
    language: str,
    target_region: str,
    transmitter_site: str,
) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO eibi_stations
           (station_name, frequency, language, target_region,
            transmitter_site, is_user_added)
           VALUES (?, ?, ?, ?, ?, 1)""",
        (station_name, frequency, language, target_region, transmitter_site),
    )
    conn.commit()
    return cur.lastrowid


# ---------------------------------------------------------------------------
# QThread worker
# ---------------------------------------------------------------------------

class EIBIUpdateWorker(QThread):
    """
    Downloads and imports the current EIBI schedule in a background thread.
    Emits progress messages and a final count (or error string) when done.
    """

    progress = pyqtSignal(str)
    finished = pyqtSignal(int)   # number of rows imported
    error = pyqtSignal(str)

    def run(self) -> None:
        try:
            self.progress.emit("Resolving EIBI download URL…")
            url = resolve_eibi_csv_url()

            self.progress.emit(f"Downloading: {url}")
            # Download with latin-1 encoding – EIBI CSV is not UTF-8
            csv_text = _download_text(url, encoding="latin-1")

            self.progress.emit("Parsing CSV data…")
            rows = parse_eibi_csv(csv_text)

            self.progress.emit(f"Importing {len(rows)} stations into database…")
            count = import_eibi_rows(rows)

            self.finished.emit(count)
        except urllib.error.URLError as exc:
            self.error.emit(
                f"Could not download EIBI data.\n\n"
                f"Check your internet connection.\n\nDetail: {exc.reason}"
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("EIBI update failed")
            self.error.emit(f"EIBI update failed: {exc}")
