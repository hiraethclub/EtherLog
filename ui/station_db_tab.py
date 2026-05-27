"""
Tab 3 – Station Database

Displays EIBI shortwave schedule data with search/filter, bulk update via
QThread worker, manual station entry, and last-update timestamp.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QMessageBox, QDialog, QFormLayout, QDialogButtonBox,
    QDoubleSpinBox, QAbstractItemView,
)
from PyQt5.QtCore import Qt

from data import eibi_importer
from data.database import get_meta
from data.eibi_importer import EIBIUpdateWorker


_COLUMNS = [
    "Station", "Frequency", "Language", "Target Region",
    "Transmitter Site", "Days", "Start UTC", "End UTC",
]


class AddStationDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Add Custom Station")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._name_edit = QLineEdit()
        form.addRow("Station Name *:", self._name_edit)

        self._freq_spin = QDoubleSpinBox()
        self._freq_spin.setRange(0, 30000)
        self._freq_spin.setDecimals(1)
        self._freq_spin.setSuffix(" kHz")
        form.addRow("Frequency:", self._freq_spin)

        self._lang_edit = QLineEdit()
        form.addRow("Language:", self._lang_edit)

        self._region_edit = QLineEdit()
        form.addRow("Target Region:", self._region_edit)

        self._txsite_edit = QLineEdit()
        form.addRow("Transmitter Site:", self._txsite_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        if not self._name_edit.text().strip():
            QMessageBox.warning(self, "Required", "Station Name is required.")
            return
        self.accept()

    def values(self) -> dict:
        return {
            "station_name": self._name_edit.text().strip(),
            "frequency": self._freq_spin.value(),
            "language": self._lang_edit.text().strip(),
            "target_region": self._region_edit.text().strip(),
            "transmitter_site": self._txsite_edit.text().strip(),
        }


class StationDbTab(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._all_rows: list[dict] = []
        self._worker: EIBIUpdateWorker | None = None
        self._build_ui()
        self._load_data()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Top controls
        top_row = QHBoxLayout()
        layout.addLayout(top_row)

        top_row.addWidget(QLabel("Search:"))
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Filter stations…")
        self._search_edit.textChanged.connect(self._apply_filter)
        top_row.addWidget(self._search_edit)

        self._update_btn = QPushButton("Update Database")
        self._update_btn.clicked.connect(self._on_update)
        top_row.addWidget(self._update_btn)

        add_btn = QPushButton("Add Custom Station")
        add_btn.clicked.connect(self._on_add_station)
        top_row.addWidget(add_btn)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        layout.addWidget(self._table)

        # Status bar row
        status_row = QHBoxLayout()
        layout.addLayout(status_row)

        self._count_label = QLabel("")
        status_row.addWidget(self._count_label)
        status_row.addStretch()

        self._last_update_label = QLabel("")
        status_row.addWidget(self._last_update_label)

        self._progress_label = QLabel("")
        layout.addWidget(self._progress_label)

    # ------------------------------------------------------------------
    # Data operations
    # ------------------------------------------------------------------

    def _load_data(self) -> None:
        self._all_rows = eibi_importer.get_all_eibi_stations()
        self._apply_filter()
        self._update_last_update_label()

        if not self._all_rows:
            self._progress_label.setText(
                "No EIBI data found. Click 'Update Database' to download the current schedule."
            )

    def _apply_filter(self) -> None:
        query = self._search_edit.text().lower()
        if query:
            filtered = [
                r for r in self._all_rows
                if query in " ".join(str(v) for v in r.values()).lower()
            ]
        else:
            filtered = self._all_rows
        self._populate_table(filtered)

    def _populate_table(self, rows: list[dict]) -> None:
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(rows))
        for row_idx, r in enumerate(rows):
            values = [
                r.get("station_name", ""),
                str(r.get("frequency", "")),
                r.get("language", ""),
                r.get("target_region", ""),
                r.get("transmitter_site", ""),
                r.get("days", ""),
                r.get("start_time_utc", ""),
                r.get("end_time_utc", ""),
            ]
            for col_idx, val in enumerate(values):
                self._table.setItem(row_idx, col_idx, QTableWidgetItem(val))
        self._table.setSortingEnabled(True)
        self._count_label.setText(f"{len(rows)} station(s) shown")

    def _update_last_update_label(self) -> None:
        ts = get_meta("eibi_last_updated")
        if ts:
            self._last_update_label.setText(f"Last updated: {ts[:19].replace('T', ' ')} UTC")
        else:
            self._last_update_label.setText("EIBI data: not yet downloaded")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_update(self) -> None:
        if self._worker and self._worker.isRunning():
            return

        self._update_btn.setEnabled(False)
        self._progress_label.setText("Starting download…")

        self._worker = EIBIUpdateWorker(parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_update_done)
        self._worker.error.connect(self._on_update_error)
        self._worker.start()

    def _on_progress(self, message: str) -> None:
        self._progress_label.setText(message)

    def _on_update_done(self, count: int) -> None:
        self._update_btn.setEnabled(True)
        self._progress_label.setText(f"Import complete: {count} stations loaded.")
        self._load_data()

    def _on_update_error(self, message: str) -> None:
        self._update_btn.setEnabled(True)
        self._progress_label.setText("Update failed.")
        QMessageBox.critical(self, "EIBI Update Failed", message)

    def _on_add_station(self) -> None:
        dlg = AddStationDialog(parent=self)
        if dlg.exec_() == dlg.Accepted:
            vals = dlg.values()
            eibi_importer.add_user_station(
                station_name=vals["station_name"],
                frequency=vals["frequency"],
                language=vals["language"],
                target_region=vals["target_region"],
                transmitter_site=vals["transmitter_site"],
            )
            self._load_data()
            QMessageBox.information(
                self, "Station Added",
                f"'{vals['station_name']}' has been added as a custom station."
            )

    def refresh(self) -> None:
        self._load_data()
