"""
Tab 5 – About

Author and application information.
"""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class AboutTab(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignTop)
        outer.setContentsMargins(40, 40, 40, 40)
        outer.setSpacing(16)

        # Application name
        title = QLabel("EtherLog")
        title_font = QFont()
        title_font.setPointSize(22)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        outer.addWidget(title)

        subtitle = QLabel("Shortwave Reception Logger")
        sub_font = QFont()
        sub_font.setPointSize(12)
        subtitle.setFont(sub_font)
        subtitle.setAlignment(Qt.AlignCenter)
        outer.addWidget(subtitle)

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        outer.addWidget(line)

        # Description
        desc = QLabel(
            "EtherLog is a cross-platform electronic QSL (eQSL) logging application "
            "for shortwave radio enthusiasts. It provides a structured form for "
            "composing reception reports to the SINPO standard, a searchable log of "
            "all sent and saved reports, an integrated EIBI shortwave schedule "
            "database, and direct email dispatch via SMTP."
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        outer.addWidget(desc)

        outer.addSpacing(16)

        # Author block
        author_label = QLabel("Author")
        author_font = QFont()
        author_font.setBold(True)
        author_label.setFont(author_font)
        author_label.setAlignment(Qt.AlignCenter)
        outer.addWidget(author_label)

        name_label = QLabel("Aisling de Grás")
        name_font = QFont()
        name_font.setPointSize(13)
        name_label.setFont(name_font)
        name_label.setAlignment(Qt.AlignCenter)
        outer.addWidget(name_label)

        email_label = QLabel(
            '<a href="mailto:aisling@hiraeth.club">aisling@hiraeth.club</a>'
        )
        email_label.setOpenExternalLinks(True)
        email_label.setAlignment(Qt.AlignCenter)
        outer.addWidget(email_label)

        outer.addSpacing(16)

        # Dedication
        ded_label = QLabel("Dedication")
        ded_font = QFont()
        ded_font.setBold(True)
        ded_label.setFont(ded_font)
        ded_label.setAlignment(Qt.AlignCenter)
        outer.addWidget(ded_label)

        ded_text = QLabel(
            "For Emma and Favourite John — who have endured more than their fair share\n"
            "of enthusiastic monologues about frequencies, fading, and far-off broadcasts.\n"
            "Your patience is deeply appreciated."
        )
        ded_text.setAlignment(Qt.AlignCenter)
        ded_italic = QFont()
        ded_italic.setItalic(True)
        ded_text.setFont(ded_italic)
        outer.addWidget(ded_text)

        outer.addSpacing(16)

        # Licence / tech note
        tech = QLabel(
            "Built with Python and PyQt5 · SQLite · EIBI schedule data"
        )
        tech.setAlignment(Qt.AlignCenter)
        tech_font = QFont()
        tech_font.setItalic(True)
        tech.setFont(tech_font)
        outer.addWidget(tech)

        outer.addStretch()
