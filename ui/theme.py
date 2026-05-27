"""Shared theme application helper."""

from PyQt5.QtWidgets import QApplication

_DARK_QSS = """
QWidget { background-color: #2b2b2b; color: #f0f0f0; }
QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #3c3f41; color: #f0f0f0; border: 1px solid #555; }
QTableWidget { background-color: #3c3f41; color: #f0f0f0; }
QHeaderView::section { background-color: #3c3f41; color: #f0f0f0; }
QPushButton { background-color: #4c5052; color: #f0f0f0; border: 1px solid #666;
              padding: 4px 8px; border-radius: 3px; }
QPushButton:hover { background-color: #5c6062; }
QPushButton:disabled { background-color: #383838; color: #666; }
QGroupBox { border: 1px solid #555; margin-top: 8px; border-radius: 4px; }
QGroupBox::title { color: #aaa; subcontrol-origin: margin; left: 8px; }
QScrollArea { border: none; }
QTabWidget::pane { border: 1px solid #555; }
QTabBar::tab { background: #3c3f41; color: #aaa; padding: 6px 14px; }
QTabBar::tab:selected { background: #2b2b2b; color: #f0f0f0; }
"""

_LIGHT_QSS = """
QWidget { background-color: #fafafa; color: #1a1a1a; }
QGroupBox { border: 1px solid #ccc; margin-top: 8px; border-radius: 4px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; }
QPushButton { padding: 4px 8px; border-radius: 3px; }
QScrollArea { border: none; }
"""


def apply_theme(theme: str) -> None:
    """Apply a named theme to the running QApplication."""
    app = QApplication.instance()
    if app is None:
        return
    if theme == "Dark":
        app.setStyleSheet(_DARK_QSS)
    elif theme == "Light":
        app.setStyleSheet(_LIGHT_QSS)
    else:
        app.setStyleSheet("")
