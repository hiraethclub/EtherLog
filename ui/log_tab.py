"""
Tab 2 – Log

Searchable, filterable table of all saved reception reports with full detail
panel, context menu, and CSV export.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import List, Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QPushButton, QLabel, QMenu, QMessageBox, QFileDialog,
    QAbstractItemView, QSplitter, QDialog, QDialogButtonBox,
    QFormLayout, QScrollArea, QFrame, QDateEdit, QTimeEdit,
    QSpinBox,
)
from PyQt5.QtCore import Qt, pyqtSignal, QDate, QTime

from models import ReportEntry
from data import log_store


# ---------------------------------------------------------------------------
# Edit dialog
# ---------------------------------------------------------------------------

_MODES = ["AM", "FM", "USB", "LSB", "CW", "DRM", "Other"]
_STATUS_EDIT = ["Draft", "Sent", "QSL Received"]
_QSL_OPTIONS = ["", "eQSL", "Physical card", "Either"]


class EditReportDialog(QDialog):
    """Full-field editor for an existing log entry."""

    def __init__(self, entry: ReportEntry, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Edit Report")
        self.resize(540, 620)
        self._entry = entry
        self._build_ui()
        self._load(entry)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        self._form = QFormLayout(container)
        self._form.setLabelAlignment(Qt.AlignRight)
        self._form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self._station = QLineEdit()
        self._form.addRow("Station Name:", self._station)

        self._freq = QLineEdit()
        self._form.addRow("Frequency (kHz):", self._freq)

        self._mode = QComboBox()
        self._mode.addItems(_MODES)
        self._form.addRow("Mode:", self._mode)

        self._date = QDateEdit()
        self._date.setCalendarPopup(True)
        self._date.setDisplayFormat("yyyy-MM-dd")
        self._form.addRow("Date UTC:", self._date)

        self._time = QTimeEdit()
        self._time.setDisplayFormat("HH:mm")
        self._form.addRow("Time UTC:", self._time)

        self._sinpo = QLineEdit()
        self._sinpo.setMaxLength(5)
        self._sinpo.setPlaceholderText("e.g. 33333")
        self._form.addRow("SINPO:", self._sinpo)

        self._status = QComboBox()
        self._status.addItems(_STATUS_EDIT)
        self._form.addRow("Status:", self._status)

        self._recipient = QLineEdit()
        self._form.addRow("Recipient Email:", self._recipient)

        self._language = QLineEdit()
        self._form.addRow("Language:", self._language)

        self._region = QLineEdit()
        self._form.addRow("Target Region:", self._region)

        self._txsite = QLineEdit()
        self._form.addRow("Transmitter Site:", self._txsite)

        self._receiver = QLineEdit()
        self._form.addRow("Receiver:", self._receiver)

        self._antenna = QLineEdit()
        self._form.addRow("Antenna:", self._antenna)

        self._software = QLineEdit()
        self._form.addRow("Software:", self._software)

        self._os = QLineEdit()
        self._form.addRow("Operating System:", self._os)

        self._qsl_pref = QComboBox()
        self._qsl_pref.addItems(_QSL_OPTIONS)
        self._form.addRow("QSL Preference:", self._qsl_pref)

        self._listener = QLineEdit()
        self._form.addRow("Listener Number:", self._listener)

        self._fading = QLineEdit()
        self._form.addRow("Fading:", self._fading)

        self._interference = QLineEdit()
        self._form.addRow("Interference:", self._interference)

        self._programme = QTextEdit()
        self._programme.setFixedHeight(70)
        self._form.addRow("Programme Details:", self._programme)

        self._remarks = QTextEdit()
        self._remarks.setFixedHeight(70)
        self._form.addRow("Remarks:", self._remarks)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _load(self, e: ReportEntry) -> None:
        self._station.setText(e.station_name)
        self._freq.setText(str(e.frequency) if e.frequency else "")
        idx = self._mode.findText(e.mode)
        if idx >= 0:
            self._mode.setCurrentIndex(idx)
        if e.date_utc:
            try:
                from datetime import datetime
                d = datetime.fromisoformat(e.date_utc)
                self._date.setDate(QDate(d.year, d.month, d.day))
            except ValueError:
                pass
        if e.time_utc:
            try:
                h, m = e.time_utc.split(":")
                self._time.setTime(QTime(int(h), int(m)))
            except (ValueError, AttributeError):
                pass
        self._sinpo.setText(e.sinpo)
        idx = self._status.findText(e.status)
        if idx >= 0:
            self._status.setCurrentIndex(idx)
        self._recipient.setText(e.recipient_email)
        self._language.setText(e.language)
        self._region.setText(e.target_region)
        self._txsite.setText(e.transmitter_site)
        self._receiver.setText(e.receiver)
        self._antenna.setText(e.antenna)
        self._software.setText(e.software)
        self._os.setText(e.operating_system)
        idx = self._qsl_pref.findText(e.qsl_preference)
        if idx >= 0:
            self._qsl_pref.setCurrentIndex(idx)
        self._listener.setText(e.listener_number)
        self._fading.setText(e.fading)
        self._interference.setText(e.interference)
        self._programme.setPlainText(e.programme_details)
        self._remarks.setPlainText(e.remarks)

    def _on_save(self) -> None:
        if not self._station.text().strip():
            QMessageBox.warning(self, "Required", "Station Name is required.")
            return
        d = self._date.date()
        t = self._time.time()
        e = self._entry
        e.station_name = self._station.text().strip()
        e.frequency = float(self._freq.text().strip() or 0)
        e.mode = self._mode.currentText()
        e.date_utc = f"{d.year():04d}-{d.month():02d}-{d.day():02d}"
        e.time_utc = f"{t.hour():02d}:{t.minute():02d}"
        e.sinpo = self._sinpo.text().strip()
        e.status = self._status.currentText()
        e.recipient_email = self._recipient.text().strip()
        e.language = self._language.text().strip()
        e.target_region = self._region.text().strip()
        e.transmitter_site = self._txsite.text().strip()
        e.receiver = self._receiver.text().strip()
        e.antenna = self._antenna.text().strip()
        e.software = self._software.text().strip()
        e.operating_system = self._os.text().strip()
        e.qsl_preference = self._qsl_pref.currentText()
        e.listener_number = self._listener.text().strip()
        e.fading = self._fading.text().strip()
        e.interference = self._interference.text().strip()
        e.programme_details = self._programme.toPlainText().strip()
        e.remarks = self._remarks.toPlainText().strip()
        log_store.update_report(e)
        self.accept()


_COLUMNS = ["Date", "Time", "Station", "Frequency", "Mode", "SINPO", "Recipient", "Status"]
_STATUS_OPTIONS = ["All", "Draft", "Sent", "QSL Received"]
_MODE_OPTIONS = ["All", "AM", "FM", "USB", "LSB", "CW", "DRM", "Other"]


class LogTab(QWidget):
    use_as_template = pyqtSignal(object)  # emits ReportEntry

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._reports: List[ReportEntry] = []
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Filter row
        filter_row = QHBoxLayout()
        layout.addLayout(filter_row)

        filter_row.addWidget(QLabel("Search:"))
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Filter across all columns…")
        self._search_edit.textChanged.connect(self._apply_filters)
        filter_row.addWidget(self._search_edit)

        filter_row.addWidget(QLabel("Status:"))
        self._status_combo = QComboBox()
        self._status_combo.addItems(_STATUS_OPTIONS)
        self._status_combo.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self._status_combo)

        filter_row.addWidget(QLabel("Mode:"))
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(_MODE_OPTIONS)
        self._mode_combo.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(self._mode_combo)

        export_btn = QPushButton("Export All to CSV")
        export_btn.clicked.connect(self._export_all_csv)
        filter_row.addWidget(export_btn)

        # Splitter: table on top, detail below
        splitter = QSplitter(Qt.Vertical)
        layout.addWidget(splitter)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        self._table.currentItemChanged.connect(self._on_selection_changed)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        splitter.addWidget(self._table)

        # Detail panel + Edit button
        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(4)

        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setPlaceholderText("Select a row to view report details.")
        detail_layout.addWidget(self._detail)

        btn_row = QHBoxLayout()
        detail_layout.addLayout(btn_row)
        self._edit_btn = QPushButton("Edit Entry…")
        self._edit_btn.setEnabled(False)
        self._edit_btn.clicked.connect(self._on_edit)
        btn_row.addWidget(self._edit_btn)
        self._delete_btn = QPushButton("Delete Entry")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(self._delete_btn)
        btn_row.addStretch()

        splitter.addWidget(detail_widget)
        splitter.setSizes([400, 220])

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Reload all reports from the database and redisplay."""
        self._reports = log_store.get_all_reports()
        self._apply_filters()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _apply_filters(self) -> None:
        query = self._search_edit.text().lower()
        status_filter = self._status_combo.currentText()
        mode_filter = self._mode_combo.currentText()

        filtered = []
        for r in self._reports:
            if status_filter != "All" and r.status != status_filter:
                continue
            if mode_filter != "All" and r.mode != mode_filter:
                continue
            if query:
                haystack = " ".join([
                    r.station_name, r.date_utc, r.time_utc, r.mode,
                    r.sinpo, r.recipient_email, r.status, r.language,
                    r.target_region,
                ]).lower()
                if query not in haystack:
                    continue
            filtered.append(r)

        self._populate_table(filtered)

    def _populate_table(self, reports: List[ReportEntry]) -> None:
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(reports))
        for row_idx, r in enumerate(reports):
            values = [
                r.date_utc, r.time_utc, r.station_name,
                str(r.frequency), r.mode, r.sinpo,
                r.recipient_email, r.status,
            ]
            for col_idx, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setData(Qt.UserRole, r.id)
                self._table.setItem(row_idx, col_idx, item)
        self._table.setSortingEnabled(True)

    def _selected_report(self) -> Optional[ReportEntry]:
        row = self._table.currentRow()
        if row < 0:
            return None
        id_item = self._table.item(row, 0)
        if id_item is None:
            return None
        report_id = id_item.data(Qt.UserRole)
        return log_store.get_report_by_id(report_id)

    def _on_selection_changed(self) -> None:
        r = self._selected_report()
        if r is None:
            self._detail.clear()
            self._edit_btn.setEnabled(False)
            self._delete_btn.setEnabled(False)
            return
        self._detail.setPlainText(self._format_detail(r))
        self._edit_btn.setEnabled(True)
        self._delete_btn.setEnabled(True)

    def _on_edit(self) -> None:
        r = self._selected_report()
        if r is None:
            return
        dlg = EditReportDialog(r, parent=self)
        if dlg.exec_() == dlg.Accepted:
            self.refresh()
            # Restore the detail panel for the updated entry
            updated = log_store.get_report_by_id(r.id)
            if updated:
                self._detail.setPlainText(self._format_detail(updated))

    def _format_detail(self, r: ReportEntry) -> str:
        lines = [
            f"Station:          {r.station_name}",
            f"Frequency:        {r.frequency} kHz",
            f"Mode:             {r.mode}",
            f"Date (UTC):       {r.date_utc}",
            f"Time (UTC):       {r.time_utc}",
            f"SINPO:            {r.sinpo}",
            f"Recipient:        {r.recipient_email}",
            f"Status:           {r.status}",
        ]
        if r.language:
            lines.append(f"Language:         {r.language}")
        if r.target_region:
            lines.append(f"Target Region:    {r.target_region}")
        if r.transmitter_site:
            lines.append(f"Transmitter Site: {r.transmitter_site}")
        if r.receiver:
            lines.append(f"Receiver:         {r.receiver}")
        if r.antenna:
            lines.append(f"Antenna:          {r.antenna}")
        if r.software:
            lines.append(f"Software:         {r.software}")
        if r.operating_system:
            lines.append(f"OS:               {r.operating_system}")
        if r.qsl_preference:
            lines.append(f"QSL Preference:   {r.qsl_preference}")
        if r.listener_number:
            lines.append(f"Listener Number:  {r.listener_number}")
        if r.fading:
            lines.append(f"Fading:           {r.fading}")
        if r.interference:
            lines.append(f"Interference:     {r.interference}")
        if r.programme_details:
            lines.append(f"\nProgramme Details:\n{r.programme_details}")
        if r.remarks:
            lines.append(f"\nRemarks:\n{r.remarks}")
        lines.append(f"\nCreated: {r.created_at}")
        return "\n".join(lines)

    def _on_delete(self) -> None:
        r = self._selected_report()
        if r is None:
            return
        answer = QMessageBox.question(
            self, "Delete Entry",
            f"Delete the log entry for {r.station_name} on {r.date_utc}?\n\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            log_store.delete_report(r.id)
            self._detail.clear()
            self._edit_btn.setEnabled(False)
            self._delete_btn.setEnabled(False)
            self.refresh()

    def _on_context_menu(self, pos) -> None:
        r = self._selected_report()
        if r is None:
            return

        menu = QMenu(self)

        edit_act = menu.addAction("Edit…")
        delete_act = menu.addAction("Delete")
        menu.addSeparator()
        resend_act = menu.addAction("Resend")
        template_act = menu.addAction("Use as Template")
        qsl_act = menu.addAction("Mark as QSL Received")
        menu.addSeparator()
        export_act = menu.addAction("Export Selected to CSV")

        action = menu.exec_(self._table.viewport().mapToGlobal(pos))
        if action == edit_act:
            self._on_edit()
        elif action == delete_act:
            self._on_delete()
        elif action == resend_act:
            self._resend(r)
        elif action == template_act:
            self.use_as_template.emit(r)
        elif action == qsl_act:
            log_store.update_report_status(r.id, "QSL Received")
            self.refresh()
        elif action == export_act:
            self._export_selected_csv(r)

    def _resend(self, r: ReportEntry) -> None:
        """Re-open the send dialog for an existing report."""
        from config import load_config, load_smtp_password
        from ui.send_dialog import SendDialog
        from data.log_store import get_active_profile

        cfg = load_config()
        profile = get_active_profile()
        if not profile:
            QMessageBox.warning(self, "No Profile", "No active sender profile.")
            return

        body_lines = [
            cfg.salutation, "", cfg.preamble, "",
            f"Station: {r.station_name}",
            f"Frequency: {r.frequency} kHz",
            f"Mode: {r.mode}",
            f"Date (UTC): {r.date_utc}",
            f"Time (UTC): {r.time_utc}",
            f"SINPO: {r.sinpo}",
            "", cfg.closing,
        ]
        if cfg.signature:
            body_lines += ["", cfg.signature]

        dlg = SendDialog(
            subject=f"Reception Report – {r.station_name} {r.date_utc}",
            body="\n".join(body_lines),
            app_config=cfg,
            from_addr=profile.email,
            parent=self,
        )
        if dlg.exec_() == dlg.Accepted:
            log_store.update_report_status(r.id, "Sent")
            self.refresh()

    def _export_selected_csv(self, r: ReportEntry) -> None:
        self._write_csv([r])

    def _export_all_csv(self) -> None:
        self._write_csv(self._reports)

    def _write_csv(self, reports: List[ReportEntry]) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save CSV", "", "CSV Files (*.csv)"
        )
        if not path:
            return
        fields = [
            "id", "station_name", "frequency", "mode", "date_utc", "time_utc",
            "sinpo", "recipient_email", "status", "language", "target_region",
            "transmitter_site", "receiver", "antenna", "software",
            "operating_system", "qsl_preference", "listener_number",
            "fading", "interference", "programme_details", "remarks", "created_at",
        ]
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=fields)
                writer.writeheader()
                for r in reports:
                    writer.writerow({f: getattr(r, f, "") for f in fields})
            QMessageBox.information(self, "Exported", f"Exported {len(reports)} report(s) to CSV.")
        except OSError as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))
