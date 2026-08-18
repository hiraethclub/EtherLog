"""
Main application window for EtherLog.

Contains a four-tab interface (New Report, Log, Station Database, Configuration)
and a persistent UTC clock in the status bar updated every second.
"""

from __future__ import annotations

from datetime import datetime, timezone

from PyQt5.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QLabel, QWidget,
)
from PyQt5.QtCore import QTimer, Qt

from models import AppConfig
from data import log_store
import config as cfg_module
from version import APP_VERSION

from ui.new_report_tab import NewReportTab
from ui.log_tab import LogTab
from ui.station_db_tab import StationDbTab
from ui.config_tab import ConfigTab
from ui.about_tab import AboutTab


class MainWindow(QMainWindow):
    def __init__(self, app_config: AppConfig, first_run: bool = False):
        super().__init__()
        self._config = app_config
        self.setWindowTitle(f"EtherLog {APP_VERSION} – Shortwave Reception Logger")
        self.resize(1320, 1170)

        self._build_ui()
        self._start_clock()

        if first_run:
            # Navigate to Configuration on first run and show a clear prompt
            self._tabs.setCurrentIndex(3)
            self.statusBar().showMessage(
                "First run: please configure your sender profile and SMTP settings in the "
                "Configuration tab before sending reports.",
                0,  # 0 = persistent (no auto-dismiss)
            )
        else:
            self._check_profile_notice()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self._tabs = QTabWidget()
        self.setCentralWidget(self._tabs)

        self._report_tab = NewReportTab(app_config=self._config)
        self._log_tab = LogTab()
        self._station_tab = StationDbTab()
        self._config_tab = ConfigTab(app_config=self._config)
        self._about_tab = AboutTab()

        self._tabs.addTab(self._report_tab, "New Report")
        self._tabs.addTab(self._log_tab, "Log")
        self._tabs.addTab(self._station_tab, "Station Database")
        self._tabs.addTab(self._config_tab, "Configuration")
        self._tabs.addTab(self._about_tab, "About")

        # Wire up cross-tab signals
        self._config_tab.config_changed.connect(self._on_config_changed)
        self._log_tab.use_as_template.connect(self._on_use_as_template)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        # Status bar: UTC clock on the right
        status = self.statusBar()
        self._clock_label = QLabel("UTC: --:--:--")
        self._clock_label.setAlignment(Qt.AlignRight)
        status.addPermanentWidget(self._clock_label)

        self._report_tab.refresh_autocomplete()

    def _start_clock(self) -> None:
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

    def _update_clock(self) -> None:
        now = datetime.now(timezone.utc)
        self._clock_label.setText(f"UTC: {now.strftime('%Y-%m-%d  %H:%M:%S')}")

    # ------------------------------------------------------------------
    # Cross-tab wiring
    # ------------------------------------------------------------------

    def _on_config_changed(self, new_config: AppConfig) -> None:
        self._config = new_config
        self._report_tab.refresh_config(new_config)
        self._check_profile_notice()
        self._apply_theme(new_config.theme)

    def _on_use_as_template(self, entry) -> None:
        """Switch to New Report tab and populate it from the selected log entry."""
        self._tabs.setCurrentIndex(0)
        self._report_tab.populate_from_report(entry)

    def _on_tab_changed(self, index: int) -> None:
        if index == 1:
            self._log_tab.refresh()
        elif index == 2:
            self._station_tab.refresh()
            self._report_tab.refresh_autocomplete()

    def _check_profile_notice(self) -> None:
        """Show a non-blocking notice on New Report if no profile is configured."""
        profile = log_store.get_active_profile()
        self._report_tab.show_notice(profile is None)

    def _apply_theme(self, theme: str) -> None:
        from ui.theme import apply_theme
        apply_theme(theme)

    def closeEvent(self, event) -> None:
        if self._report_tab.has_unsaved_data():
            from PyQt5.QtWidgets import QMessageBox
            answer = QMessageBox.question(
                self,
                "Unsaved Report",
                "The New Report form has unsaved data. Discard and quit?",
                QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            if answer == QMessageBox.Cancel:
                event.ignore()
                return
        event.accept()
