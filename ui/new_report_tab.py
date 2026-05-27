"""
Tab 1 – New Report

Handles the reception report form, SINPO entry, EIBI autofill with dirty-flag
protection, clipboard copy, and the Send via Email dialog.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QComboBox, QDateEdit, QTimeEdit, QTextEdit,
    QPushButton, QCompleter, QMessageBox, QScrollArea, QFrame,
    QSizePolicy, QToolTip, QGroupBox, QApplication,
    QDialog, QDialogButtonBox, QListWidget,
)
from PyQt5.QtCore import Qt, QStringListModel, QDate, QTime
from PyQt5.QtGui import QFont

from models import AppConfig, ReportEntry, OPTIONAL_FIELD_LABELS
from data import eibi_importer, log_store
import config as cfg_module


SINPO_DESCRIPTIONS = {
    "S": ("Signal Strength", {
        "1": "Barely perceptible",
        "2": "Weak",
        "3": "Moderate",
        "4": "Good",
        "5": "Excellent",
    }),
    "I": ("Interference", {
        "1": "Extreme interference",
        "2": "Heavy interference",
        "3": "Moderate interference",
        "4": "Slight interference",
        "5": "No interference",
    }),
    "N": ("Noise Level", {
        "1": "Very noisy",
        "2": "Noisy",
        "3": "Moderate noise",
        "4": "Slight noise",
        "5": "No noise",
    }),
    "P": ("Propagation disturbance", {
        "1": "Severe fading",
        "2": "Considerable fading",
        "3": "Moderate fading",
        "4": "Slight fading",
        "5": "No fading",
    }),
    "O": ("Overall merit", {
        "1": "Unusable",
        "2": "Poor",
        "3": "Fair",
        "4": "Good",
        "5": "Excellent",
    }),
}

MODES = ["AM", "FM", "USB", "LSB", "CW", "DRM", "Other"]
QSL_OPTIONS = ["eQSL", "Physical card", "Either"]


class NewReportTab(QWidget):
    def __init__(self, app_config: AppConfig, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._config = app_config

        # Dirty flags for autofill-protected fields. A True flag means the
        # user has manually edited that field and autofill must not overwrite it.
        self._dirty: dict[str, bool] = {
            "frequency": False,
            "language": False,
            "target_region": False,
        }

        self._build_ui()
        self._refresh_optional_visibility()
        self._prefill_defaults()

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
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Notice banner (shown when no profile configured)
        self._notice = QLabel(
            "No sender profile configured. "
            "Please complete setup in the Configuration tab before sending reports."
        )
        self._notice.setStyleSheet("background: #fff3cd; padding: 6px; border-radius: 4px;")
        self._notice.setWordWrap(True)
        self._notice.setVisible(False)
        main_layout.addWidget(self._notice)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        main_layout.addLayout(form)

        # --- Required fields ---
        self._station_edit = QLineEdit()
        self._station_edit.setPlaceholderText("Start typing to search…")
        self._completer = QCompleter()
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchContains)
        self._station_edit.setCompleter(self._completer)
        self._completer.activated.connect(self._on_station_selected)
        form.addRow("Station Name *:", self._station_edit)

        self._freq_edit = QLineEdit()
        self._freq_edit.setPlaceholderText("kHz")
        self._freq_edit.textEdited.connect(lambda: self._mark_dirty("frequency"))
        self._freq_lookup_btn = QPushButton("Look up")
        self._freq_lookup_btn.setToolTip("Find stations at this frequency in the EIBI database")
        self._freq_lookup_btn.clicked.connect(self._on_freq_lookup)
        freq_container = QWidget()
        freq_container.setMaximumWidth(300)
        freq_hl = QHBoxLayout(freq_container)
        freq_hl.setContentsMargins(0, 0, 0, 0)
        freq_hl.setSpacing(4)
        freq_hl.addWidget(self._freq_edit)
        freq_hl.addWidget(self._freq_lookup_btn)
        form.addRow("Frequency (kHz) *:", freq_container)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(MODES)
        form.addRow("Mode *:", self._mode_combo)

        self._date_edit = QDateEdit()
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("yyyy-MM-dd")
        now_utc = datetime.now(timezone.utc)
        self._date_edit.setDate(QDate(now_utc.year, now_utc.month, now_utc.day))
        form.addRow("Date UTC *:", self._date_edit)

        self._time_edit = QTimeEdit()
        self._time_edit.setDisplayFormat("HH:mm")
        self._time_edit.setTime(QTime(now_utc.hour, now_utc.minute))
        form.addRow("Time UTC *:", self._time_edit)

        # SINPO block
        sinpo_widget = self._build_sinpo_widget()
        form.addRow("SINPO *:", sinpo_widget)

        # --- Optional fields (visibility controlled by config) ---
        self._lang_edit = QLineEdit()
        self._lang_edit.textEdited.connect(lambda: self._mark_dirty("language"))
        self._lang_row = ("Language:", self._lang_edit)
        form.addRow(*self._lang_row)
        self._lang_edit._form_key = "language"

        self._region_edit = QLineEdit()
        self._region_edit.textEdited.connect(lambda: self._mark_dirty("target_region"))
        self._region_row = ("Target Region:", self._region_edit)
        form.addRow(*self._region_row)

        self._txsite_edit = QLineEdit()
        form.addRow("Transmitter Site / Relay:", self._txsite_edit)

        self._receiver_edit = QLineEdit()
        form.addRow("Receiver:", self._receiver_edit)

        self._antenna_edit = QLineEdit()
        form.addRow("Antenna:", self._antenna_edit)

        self._software_edit = QLineEdit()
        form.addRow("Software Used:", self._software_edit)

        self._os_edit = QLineEdit()
        form.addRow("Operating System:", self._os_edit)

        self._qsl_combo = QComboBox()
        self._qsl_combo.addItem("(not specified)")
        self._qsl_combo.addItems(QSL_OPTIONS)
        form.addRow("QSL Preference:", self._qsl_combo)

        self._listener_edit = QLineEdit()
        form.addRow("Listener / Membership Number:", self._listener_edit)

        self._fading_edit = QLineEdit()
        form.addRow("Signal Fading Observations:", self._fading_edit)

        self._interference_edit = QLineEdit()
        form.addRow("Interference Sources:", self._interference_edit)

        self._programme_edit = QTextEdit()
        self._programme_edit.setFixedHeight(80)
        form.addRow("Programme Details Heard:", self._programme_edit)

        self._remarks_edit = QTextEdit()
        self._remarks_edit.setFixedHeight(80)
        form.addRow("Remarks:", self._remarks_edit)

        # Map field keys → their QWidget for bulk show/hide
        self._optional_widgets: dict[str, list[QWidget]] = {
            "language": [self._lang_edit],
            "target_region": [self._region_edit],
            "transmitter_site": [self._txsite_edit],
            "receiver": [self._receiver_edit],
            "antenna": [self._antenna_edit],
            "software": [self._software_edit],
            "operating_system": [self._os_edit],
            "qsl_preference": [self._qsl_combo],
            "listener_number": [self._listener_edit],
            "fading": [self._fading_edit],
            "interference": [self._interference_edit],
            "programme_details": [self._programme_edit],
            "remarks": [self._remarks_edit],
        }

        # Keep references to form-row labels for show/hide
        self._form = form
        self._form_rows: dict[str, int] = {}
        self._build_form_row_map()

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        main_layout.addLayout(btn_layout)

        self._copy_btn = QPushButton("Copy to Clipboard")
        self._copy_btn.clicked.connect(self._on_copy)
        btn_layout.addWidget(self._copy_btn)

        self._save_btn = QPushButton("Save to Log")
        self._save_btn.clicked.connect(self._on_save_draft)
        self._save_btn.setToolTip("Save this report as a Draft without sending")
        btn_layout.addWidget(self._save_btn)

        self._send_btn = QPushButton("Send via Email")
        self._send_btn.clicked.connect(self._on_send)
        btn_layout.addWidget(self._send_btn)

        clear_btn = QPushButton("Clear Form")
        clear_btn.clicked.connect(self._on_clear)
        btn_layout.addStretch()
        btn_layout.addWidget(clear_btn)

    def _build_sinpo_widget(self) -> QWidget:
        """Build five dropdowns (one per SINPO letter) plus a reference panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        dropdowns_row = QHBoxLayout()
        layout.addLayout(dropdowns_row)

        self._sinpo_combos: dict[str, QComboBox] = {}
        for letter, (label, values) in SINPO_DESCRIPTIONS.items():
            col = QVBoxLayout()
            lbl = QLabel(f"<b>{letter}</b>")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setToolTip(f"{label}")
            col.addWidget(lbl)

            combo = QComboBox()
            for val, desc in values.items():
                combo.addItem(val, userData=desc)
            combo.setCurrentIndex(2)  # default 3 (moderate)
            combo.setToolTip(f"{label}")
            col.addWidget(combo)
            self._sinpo_combos[letter] = combo
            dropdowns_row.addLayout(col)

        # Always-visible reference panel — one label per entry so Qt can
        # compute each label's word-wrap height independently (a single
        # multi-line HTML label in a QGroupBox miscalculates its height).
        ref = QGroupBox("SINPO Reference")
        ref_layout = QVBoxLayout(ref)
        ref_layout.setContentsMargins(6, 4, 6, 4)
        ref_layout.setSpacing(2)
        for letter, (label, values) in SINPO_DESCRIPTIONS.items():
            val_strs = ", ".join(f"{k}={v}" for k, v in values.items())
            entry = QLabel(f"<b>{letter}</b> – {label}: {val_strs}")
            entry.setWordWrap(True)
            entry.setTextFormat(Qt.RichText)
            ref_layout.addWidget(entry)
        layout.addWidget(ref)

        widget.setMaximumWidth(540)
        return widget

    def _build_form_row_map(self) -> None:
        """Build a map from optional field key → QFormLayout row index."""
        key_order = [
            "language", "target_region", "transmitter_site", "receiver",
            "antenna", "software", "operating_system", "qsl_preference",
            "listener_number", "fading", "interference",
            "programme_details", "remarks",
        ]
        # Required rows come first (station, freq, mode, date, time, sinpo = 6)
        for i, key in enumerate(key_order):
            self._form_rows[key] = 6 + i

    # ------------------------------------------------------------------
    # Public API called by main window
    # ------------------------------------------------------------------

    def refresh_config(self, app_config: AppConfig) -> None:
        """Called whenever configuration changes."""
        self._config = app_config
        self._refresh_optional_visibility()
        self._prefill_defaults()

    def refresh_autocomplete(self) -> None:
        """Rebuild completer from EIBI + log station names."""
        eibi_names = eibi_importer.get_eibi_station_names()
        log_names = log_store.get_known_station_names()
        combined = sorted(set(eibi_names) | set(log_names))
        model = QStringListModel(combined)
        self._completer.setModel(model)

    def populate_from_report(self, entry: ReportEntry) -> None:
        """Pre-fill the form from a saved report (Use as Template)."""
        self._on_clear()
        self._station_edit.setText(entry.station_name)
        self._freq_edit.setText(str(entry.frequency) if entry.frequency else "")
        idx = self._mode_combo.findText(entry.mode)
        if idx >= 0:
            self._mode_combo.setCurrentIndex(idx)
        if entry.date_utc:
            try:
                d = datetime.fromisoformat(entry.date_utc)
                self._date_edit.setDate(QDate(d.year, d.month, d.day))
            except ValueError:
                pass
        if entry.time_utc:
            try:
                parts = entry.time_utc.split(":")
                self._time_edit.setTime(QTime(int(parts[0]), int(parts[1])))
            except (ValueError, IndexError):
                pass
        if entry.sinpo and len(entry.sinpo) == 5:
            for i, letter in enumerate("SINPO"):
                idx = self._sinpo_combos[letter].findText(entry.sinpo[i])
                if idx >= 0:
                    self._sinpo_combos[letter].setCurrentIndex(idx)
        self._lang_edit.setText(entry.language)
        self._region_edit.setText(entry.target_region)
        self._txsite_edit.setText(entry.transmitter_site)
        self._receiver_edit.setText(entry.receiver)
        self._antenna_edit.setText(entry.antenna)
        self._software_edit.setText(entry.software)
        self._os_edit.setText(entry.operating_system)
        qsl_idx = self._qsl_combo.findText(entry.qsl_preference)
        if qsl_idx >= 0:
            self._qsl_combo.setCurrentIndex(qsl_idx)
        self._listener_edit.setText(entry.listener_number)
        self._fading_edit.setText(entry.fading)
        self._interference_edit.setText(entry.interference)
        self._programme_edit.setPlainText(entry.programme_details)
        self._remarks_edit.setPlainText(entry.remarks)

    def show_notice(self, visible: bool) -> None:
        self._notice.setVisible(visible)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _prefill_defaults(self) -> None:
        cfg = self._config
        if not self._receiver_edit.text():
            self._receiver_edit.setText(cfg.default_receiver)
        if not self._antenna_edit.text():
            self._antenna_edit.setText(cfg.default_antenna)
        if not self._software_edit.text():
            self._software_edit.setText(cfg.default_software)
        if not self._os_edit.text():
            self._os_edit.setText(cfg.default_os)

        profile = log_store.get_active_profile()
        if profile and not self._listener_edit.text():
            self._listener_edit.setText(profile.listener_number)

    def _refresh_optional_visibility(self) -> None:
        """Show/hide optional fields according to the visible_fields config."""
        for key, widgets in self._optional_widgets.items():
            visible = self._config.visible_fields.get(key, True)
            row = self._form_rows.get(key, -1)
            for w in widgets:
                w.setVisible(visible)
            # Also hide the label item in the form layout
            if row >= 0:
                label_item = self._form.itemAt(row, QFormLayout.LabelRole)
                if label_item and label_item.widget():
                    label_item.widget().setVisible(visible)

    def _mark_dirty(self, field: str) -> None:
        """Signal that the user has manually edited a protected field."""
        self._dirty[field] = True

    def _sinpo_code(self) -> str:
        return "".join(
            self._sinpo_combos[l].currentText() for l in "SINPO"
        )

    def _on_station_selected(self, name: str) -> None:
        """Called when user picks a station from autocomplete."""
        if not self._config.eibi_autofill:
            return
        data = eibi_importer.get_eibi_data_for_station(name)
        if not data:
            return
        # Only autofill fields that are not dirty (user hasn't manually edited them)
        if not self._dirty["frequency"] and data.get("frequency"):
            self._freq_edit.setText(str(data["frequency"]))
        if not self._dirty["language"] and data.get("language"):
            self._lang_edit.setText(data["language"])
        if not self._dirty["target_region"] and data.get("target_region"):
            self._region_edit.setText(data["target_region"])

    def has_unsaved_data(self) -> bool:
        """True if the form contains meaningful content that has not been saved."""
        return bool(
            self._station_edit.text().strip()
            or self._freq_edit.text().strip()
            or self._programme_edit.toPlainText().strip()
            or self._remarks_edit.toPlainText().strip()
        )

    def _on_freq_lookup(self) -> None:
        freq_text = self._freq_edit.text().strip()
        if not freq_text:
            QMessageBox.information(self, "Frequency Lookup", "Enter a frequency in kHz first.")
            return
        try:
            freq = float(freq_text)
        except ValueError:
            QMessageBox.warning(self, "Frequency Lookup", "Not a valid frequency value.")
            return

        stations = eibi_importer.get_eibi_stations_for_frequency(freq)
        if not stations:
            QMessageBox.information(
                self, "Frequency Lookup",
                f"No stations found at {freq} kHz (±1 kHz) in the EIBI database.\n\n"
                "Try downloading the latest schedule in the Station Database tab.",
            )
            return

        if len(stations) == 1:
            self._apply_freq_result(stations[0])
            return

        # Multiple matches — let the user pick
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Stations at {freq} kHz")
        dlg.resize(520, 320)
        vbox = QVBoxLayout(dlg)
        vbox.addWidget(QLabel(
            f"{len(stations)} station(s) found at {freq} kHz — select one to fill the form:"
        ))
        lst = QListWidget()
        for s in stations:
            parts = [s.get("station_name", "")]
            if s.get("language"):
                parts.append(s["language"])
            if s.get("target_region"):
                parts.append(s["target_region"])
            start = s.get("start_time_utc", "")
            end = s.get("end_time_utc", "")
            if start or end:
                parts.append(f"{start}–{end} UTC")
            if s.get("days"):
                parts.append(s["days"])
            lst.addItem(" · ".join(parts))
        lst.setCurrentRow(0)
        lst.itemDoubleClicked.connect(lambda _: dlg.accept())
        vbox.addWidget(lst)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        vbox.addWidget(btns)

        if dlg.exec_() == QDialog.Accepted:
            row = lst.currentRow()
            if row >= 0:
                self._apply_freq_result(stations[row])

    def _apply_freq_result(self, station: dict) -> None:
        """Fill form fields from a frequency-lookup result (explicit user action)."""
        if station.get("station_name"):
            self._station_edit.setText(station["station_name"])
        if station.get("language"):
            self._lang_edit.setText(station["language"])
            self._dirty["language"] = True
        if station.get("target_region"):
            self._region_edit.setText(station["target_region"])
            self._dirty["target_region"] = True
        if station.get("transmitter_site"):
            self._txsite_edit.setText(station["transmitter_site"])
        self._dirty["frequency"] = True

    def _on_clear(self) -> None:
        """Reset the form and clear all dirty flags."""
        self._station_edit.clear()
        self._freq_edit.clear()
        self._mode_combo.setCurrentIndex(0)
        now_utc = datetime.now(timezone.utc)
        self._date_edit.setDate(QDate(now_utc.year, now_utc.month, now_utc.day))
        self._time_edit.setTime(QTime(now_utc.hour, now_utc.minute))
        for combo in self._sinpo_combos.values():
            combo.setCurrentIndex(2)
        self._lang_edit.clear()
        self._region_edit.clear()
        self._txsite_edit.clear()
        self._receiver_edit.clear()
        self._antenna_edit.clear()
        self._software_edit.clear()
        self._os_edit.clear()
        self._qsl_combo.setCurrentIndex(0)
        self._listener_edit.clear()
        self._fading_edit.clear()
        self._interference_edit.clear()
        self._programme_edit.clear()
        self._remarks_edit.clear()
        # Reset dirty flags
        self._dirty = {k: False for k in self._dirty}
        self._prefill_defaults()

    def _validate(self) -> bool:
        if not self._station_edit.text().strip():
            QMessageBox.warning(self, "Validation", "Station Name is required.")
            return False
        return True

    def _build_report_entry(self) -> ReportEntry:
        profile = log_store.get_active_profile()
        d = self._date_edit.date()
        t = self._time_edit.time()
        entry = ReportEntry(
            station_name=self._station_edit.text().strip(),
            frequency=float(self._freq_edit.text().strip() or 0),
            mode=self._mode_combo.currentText(),
            date_utc=f"{d.year():04d}-{d.month():02d}-{d.day():02d}",
            time_utc=f"{t.hour():02d}:{t.minute():02d}",
            sinpo=self._sinpo_code(),
            language=self._lang_edit.text().strip(),
            target_region=self._region_edit.text().strip(),
            transmitter_site=self._txsite_edit.text().strip(),
            receiver=self._receiver_edit.text().strip(),
            antenna=self._antenna_edit.text().strip(),
            software=self._software_edit.text().strip(),
            operating_system=self._os_edit.text().strip(),
            qsl_preference=(
                self._qsl_combo.currentText()
                if self._qsl_combo.currentIndex() > 0
                else ""
            ),
            listener_number=self._listener_edit.text().strip(),
            fading=self._fading_edit.text().strip(),
            interference=self._interference_edit.text().strip(),
            programme_details=self._programme_edit.toPlainText().strip(),
            remarks=self._remarks_edit.toPlainText().strip(),
            sender_profile_id=profile.id if profile else 0,
        )
        return entry

    def _compose_report_text(self, entry: ReportEntry) -> str:
        """Format the reception report as plain text for email / clipboard."""
        cfg = self._config
        visible = cfg.visible_fields

        lines = [cfg.salutation, "", cfg.preamble, ""]

        if entry.report_number > 0:
            lines.append(f"Report Number: #{entry.report_number:04d}")

        def add(label: str, value: str, key: Optional[str] = None) -> None:
            if key is None or (visible.get(key, True) and value):
                lines.append(f"{label}: {value}")

        add("Station", entry.station_name)
        add("Frequency", f"{entry.frequency} kHz" if entry.frequency else "")
        add("Mode", entry.mode)
        add("Date (UTC)", entry.date_utc)
        add("Time (UTC)", entry.time_utc)
        add("SINPO", entry.sinpo)
        add("Language", entry.language, "language")
        add("Target Region", entry.target_region, "target_region")
        add("Transmitter Site / Relay", entry.transmitter_site, "transmitter_site")
        add("Receiver", entry.receiver, "receiver")
        add("Antenna", entry.antenna, "antenna")
        add("Software Used", entry.software, "software")
        add("Operating System", entry.operating_system, "operating_system")
        add("QSL Preference", entry.qsl_preference, "qsl_preference")
        add("Listener / Membership Number", entry.listener_number, "listener_number")
        add("Signal Fading Observations", entry.fading, "fading")
        add("Interference Sources", entry.interference, "interference")

        if visible.get("programme_details", True) and entry.programme_details:
            lines.append("Programme Details Heard:")
            lines.append(entry.programme_details)
        if visible.get("remarks", True) and entry.remarks:
            lines.append("Remarks:")
            lines.append(entry.remarks)

        lines.append("")
        lines.append(cfg.closing)

        if cfg.signature:
            lines.append("")
            lines.append(cfg.signature)

        return "\n".join(lines)

    def _on_save_draft(self) -> None:
        if not self._validate():
            return
        entry = self._build_report_entry()
        entry.report_number = log_store.get_next_report_number()
        entry.status = "Draft"
        log_store.save_report(entry)
        self.refresh_autocomplete()
        QMessageBox.information(self, "Saved", f"Report #{entry.report_number:04d} saved to log as Draft.")

    def _on_copy(self) -> None:
        if not self._validate():
            return
        entry = self._build_report_entry()
        entry.report_number = log_store.get_next_report_number()
        text = self._compose_report_text(entry)
        QApplication.clipboard().setText(text)
        entry.status = "Draft"
        log_store.save_report(entry)
        self.refresh_autocomplete()
        QMessageBox.information(
            self, "Copied",
            f"Report #{entry.report_number:04d} copied to clipboard and saved to log as Draft.",
        )

    def _on_send(self) -> None:
        if not self._validate():
            return

        profile = log_store.get_active_profile()
        if not profile:
            QMessageBox.warning(
                self,
                "No Sender Profile",
                "Please create and activate a sender profile in the Configuration tab.",
            )
            return

        entry = self._build_report_entry()
        entry.report_number = log_store.get_next_report_number()
        text = self._compose_report_text(entry)
        subject = f"Reception Report – {entry.station_name} {entry.date_utc}"

        from ui.send_dialog import SendDialog
        dlg = SendDialog(
            subject=subject,
            body=text,
            app_config=self._config,
            from_addr=profile.email,
            parent=self,
        )
        if dlg.exec_() == dlg.Accepted:
            recipient = dlg.get_recipient()
            entry.recipient_email = recipient
            entry.status = "Sent"
            log_store.save_report(entry)
            QMessageBox.information(self, "Sent", f"Report #{entry.report_number:04d} saved to log as Sent.")
            self.refresh_autocomplete()
