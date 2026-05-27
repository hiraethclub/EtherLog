"""
EtherLog – Shortwave Reception Logger
Entry point.
"""

import sys
import logging

from PyQt5.QtWidgets import QApplication

import config as cfg_module
from data.database import init_db
from ui.main_window import MainWindow


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = QApplication(sys.argv)
    app.setApplicationName("EtherLog")
    app.setOrganizationName("EtherLog")

    # Detect first run before creating the config file
    first_run = cfg_module.is_first_run()

    # Initialise SQLite (creates tables / runs migrations)
    init_db(cfg_module.get_db_path())

    # Load or create application configuration
    app_config = cfg_module.load_config()

    # Apply saved theme before showing the window
    from ui.theme import apply_theme
    apply_theme(app_config.theme)

    window = MainWindow(app_config=app_config, first_run=first_run)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
