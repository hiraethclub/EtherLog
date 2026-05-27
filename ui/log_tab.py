"""
Tab 2 – Log

Searchable, filterable table of all saved reception reports with full detail
panel, context menu, and CSV export.
"""

import csv
import io
from datetime import datetime, timezone
from typing import List, Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QPushButton, QLabel, QMenu, QMessageBox, QFileDialog,
    QAbstractItemView, QSplitter,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QCursor

from models import ReportEntry
from data import log_store


_COLUMNS = ["Date", "Time", "Station", "Frequency", "Mode", "SINPO", "Recipient", "Status"]
_STATUS_OPTIONS = ["All", "Draft", "Sent", "QSL Received"]
_MODE_OPTIONS = ["All", "AM", "FM", "USB", "LSB", "CW", "DRM", "Other"]


class LogTab(QWidget):
    use_as_template = pyqtSignal(object)  # emits ReportEntry

    def __init__(self, parent: QWidget | None = None):
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

        # Detail panel
        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setPlaceholderText("Select a row to view report details.")
        splitter.addWidget(self._detail)
        splitter.setSizes([400, 200])

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
            return
        self._detail.setPlainText(self._format_detail(r))

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

    def _on_context_menu(self, pos) -> None:
        r = self._selected_report()
        if r is None:
            return

        menu = QMenu(self)

        resend_act = menu.addAction("Resend")
        template_act = menu.addAction("Use as Template")
        qsl_act = menu.addAction("Mark as QSL Received")
        menu.addSeparator()
        export_act = menu.addAction("Export Selected to CSV")

        action = menu.exec_(self._table.viewport().mapToGlobal(pos))
        if action == resend_act:
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
