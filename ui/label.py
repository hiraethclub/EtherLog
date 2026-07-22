"""
Airmail QSL label rendering, preview, and printing.

Produces a small self-adhesive label — sized for the address side of a postcard —
carrying the recipient (station) postal address, an optional return address, and
the classic red/blue "candy stripe" airmail border with a PAR AVION / BY AIR MAIL
marking.  The same paint routine drives both the on-screen preview and the
printer/PDF output so what you see is what prints.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from PyQt5.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QCheckBox, QComboBox, QPushButton, QMessageBox, QFileDialog, QSizePolicy,
    QFormLayout,
)
from PyQt5.QtCore import Qt, QRectF, QRect
from PyQt5.QtGui import QPainter, QColor, QFont, QFontMetrics, QPainterPath, QPen
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog

from models import ReportEntry, SenderProfile


# ---------------------------------------------------------------------------
# Label sizes (physical, in millimetres)
# ---------------------------------------------------------------------------

# (label, width_mm, height_mm)
LABEL_SIZES: List[Tuple[str, float, float]] = [
    ("Standard (90 × 50 mm)", 90.0, 50.0),
    ("Large (100 × 60 mm)", 100.0, 60.0),
    ("Small (70 × 38 mm)", 70.0, 38.0),
    ("Square (70 × 70 mm)", 70.0, 70.0),
]

_AIRMAIL_RED = QColor("#d0021b")
_AIRMAIL_BLUE = QColor("#0b4da2")


# ---------------------------------------------------------------------------
# Painting
# ---------------------------------------------------------------------------

def _draw_airmail_border(
    painter: QPainter, rect: QRectF, thickness: float, px_per_mm: float
) -> None:
    """Draw the diagonal red/blue candy-stripe border inside the frame region."""
    inner = rect.adjusted(thickness, thickness, -thickness, -thickness)

    frame = QPainterPath()
    frame.addRect(rect)
    hole = QPainterPath()
    hole.addRect(inner)
    frame = frame.subtracted(hole)

    painter.save()
    painter.setClipPath(frame)
    painter.setPen(Qt.NoPen)

    bar = max(1.0, 2.1 * px_per_mm)   # width of each coloured stripe
    painter.translate(rect.center())
    painter.rotate(45)
    diag = math.hypot(rect.width(), rect.height())

    x = -diag
    i = 0
    while x < diag:
        colour = _AIRMAIL_RED if i % 2 == 0 else _AIRMAIL_BLUE
        painter.fillRect(QRectF(x, -diag / 2, bar, diag), colour)
        x += bar * 2   # coloured stripe followed by an equal white gap
        i += 1
    painter.restore()

    # Crisp thin outlines around the outer and inner edges of the frame.
    painter.save()
    pen = QPen(QColor("#333333"))
    pen.setWidthF(max(0.4, 0.25 * px_per_mm))
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawRect(rect)
    painter.drawRect(inner)
    painter.restore()


def _draw_airmail_badge(
    painter: QPainter, rect: QRectF, px_per_mm: float
) -> None:
    """Draw the blue PAR AVION / BY AIR MAIL badge inside the given rect."""
    painter.save()
    painter.setPen(Qt.NoPen)
    painter.setBrush(_AIRMAIL_BLUE)
    radius = 1.2 * px_per_mm
    painter.drawRoundedRect(rect, radius, radius)

    painter.setPen(QColor("white"))
    top = QRectF(rect.left(), rect.top(), rect.width(), rect.height() * 0.58)
    bottom = QRectF(
        rect.left(), rect.top() + rect.height() * 0.55,
        rect.width(), rect.height() * 0.45,
    )

    f = QFont(painter.font())
    f.setBold(True)
    f.setPixelSize(max(6, round(2.9 * px_per_mm)))
    painter.setFont(f)
    painter.drawText(top, Qt.AlignCenter, "PAR AVION")

    f2 = QFont(painter.font())
    f2.setBold(False)
    f2.setPixelSize(max(5, round(1.9 * px_per_mm)))
    painter.setFont(f2)
    painter.drawText(bottom, Qt.AlignCenter, "BY AIR MAIL")
    painter.restore()


def _draw_text_block(
    painter: QPainter,
    rect: QRectF,
    heading: str,
    body: str,
    heading_mm: float,
    body_mm: float,
    px_per_mm: float,
    auto_fit: bool = False,
) -> None:
    """Draw a small grey heading followed by a wrapped body text block.

    When ``auto_fit`` is set the body font shrinks (down to a legible floor) so
    a long address still fits inside ``rect`` rather than overflowing the label.
    """
    painter.save()
    y = rect.top()

    if heading:
        hf = QFont(painter.font())
        hf.setBold(True)
        hf.setPixelSize(max(5, round(heading_mm * px_per_mm)))
        painter.setFont(hf)
        painter.setPen(QColor("#888888"))
        line_h = painter.fontMetrics().height()
        painter.drawText(
            QRectF(rect.left(), y, rect.width(), line_h),
            Qt.AlignLeft | Qt.AlignVCenter, heading,
        )
        y += line_h + 0.6 * px_per_mm

    bf = QFont(painter.font())
    bf.setBold(False)
    size = max(6, round(body_mm * px_per_mm))
    flags = Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap
    bounds = QRect(0, 0, max(1, int(rect.width())), 1_000_000)

    if auto_fit:
        avail_h = rect.bottom() - y
        floor = max(5, round(2.1 * px_per_mm))
        while size > floor:
            bf.setPixelSize(size)
            needed = QFontMetrics(bf).boundingRect(bounds, flags, body).height()
            if needed <= avail_h:
                break
            size -= 1

    bf.setPixelSize(size)
    painter.setFont(bf)
    painter.setPen(QColor("#111111"))
    painter.drawText(
        QRectF(rect.left(), y, rect.width(), rect.bottom() - y),
        flags, body,
    )
    painter.restore()


def paint_label(
    painter: QPainter,
    rect: QRectF,
    px_per_mm: float,
    recipient: str,
    return_address: str,
    include_return: bool,
    airmail: bool,
) -> None:
    """Paint a complete airmail label into ``rect`` (device coordinates)."""
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.TextAntialiasing, True)

    # White label background.
    painter.fillRect(rect, QColor("white"))

    border = 3.0 * px_per_mm if airmail else 0.0
    if airmail:
        _draw_airmail_border(painter, rect, border, px_per_mm)

    pad = 2.4 * px_per_mm
    content = rect.adjusted(border + pad, border + pad, -(border + pad), -(border + pad))

    # Airmail badge, top-left. Its height scales with the label so a small
    # label still leaves room for the addresses below it.
    show_return = include_return and bool(return_address.strip())
    y_cursor = content.top()
    if airmail:
        badge_h = min(9 * px_per_mm, content.height() * 0.26)
        badge_w = min(content.width() * 0.42, 34 * px_per_mm)
        badge = QRectF(content.left(), content.top(), badge_w, badge_h)
        _draw_airmail_badge(painter, badge, px_per_mm)
        y_cursor = badge.bottom() + 1.6 * px_per_mm

    # Give the return block its natural (measured) height so it never crowds the
    # recipient on a roomy label, but cap it so the recipient always keeps at
    # least half of the remaining space on a small one. Both blocks auto-fit.
    remaining = content.bottom() - y_cursor
    if show_return:
        ret_text = return_address.strip()
        ret_head_px = max(5, round(2.1 * px_per_mm))
        ret_body_px = max(5, round(2.6 * px_per_mm))
        mf = QFont(painter.font())
        mf.setPixelSize(ret_body_px)
        flags = Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap
        body_h = QFontMetrics(mf).boundingRect(
            QRect(0, 0, max(1, int(content.width())), 1_000_000), flags, ret_text
        ).height()
        natural = ret_head_px + 0.6 * px_per_mm + body_h
        ret_h = min(natural, remaining * 0.5)
        ret_rect = QRectF(content.left(), y_cursor, content.width(), ret_h)
        _draw_text_block(
            painter, ret_rect, "FROM:", ret_text,
            heading_mm=2.1, body_mm=2.6, px_per_mm=px_per_mm, auto_fit=True,
        )
        y_cursor = ret_rect.bottom() + 1.2 * px_per_mm

    # Recipient address — the dominant block, filling the remaining space.
    indent = 4 * px_per_mm if show_return else 0.0
    rec_rect = QRectF(
        content.left() + indent, y_cursor,
        content.width() - indent, content.bottom() - y_cursor,
    )
    _draw_text_block(
        painter, rec_rect, "TO:", recipient.strip() or "(no address)",
        heading_mm=2.3, body_mm=4.0, px_per_mm=px_per_mm, auto_fit=True,
    )

    painter.restore()


# ---------------------------------------------------------------------------
# Preview widget
# ---------------------------------------------------------------------------

class _LabelPreview(QWidget):
    """Scales the label to fit while preserving its physical aspect ratio."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumHeight(230)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._w_mm = LABEL_SIZES[0][1]
        self._h_mm = LABEL_SIZES[0][2]
        self._recipient = ""
        self._return = ""
        self._include_return = True
        self._airmail = True

    def set_params(
        self, w_mm: float, h_mm: float, recipient: str, return_address: str,
        include_return: bool, airmail: bool,
    ) -> None:
        self._w_mm, self._h_mm = w_mm, h_mm
        self._recipient = recipient
        self._return = return_address
        self._include_return = include_return
        self._airmail = airmail
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#c8ccd2"))

        avail_w = self.width() - 24
        avail_h = self.height() - 24
        if avail_w <= 0 or avail_h <= 0:
            return

        scale = min(avail_w / self._w_mm, avail_h / self._h_mm)
        label_w = self._w_mm * scale
        label_h = self._h_mm * scale
        x = (self.width() - label_w) / 2
        y = (self.height() - label_h) / 2
        rect = QRectF(x, y, label_w, label_h)

        # Soft drop shadow so the label reads as a physical sticker.
        painter.fillRect(rect.translated(3, 3), QColor(0, 0, 0, 40))

        paint_label(
            painter, rect, px_per_mm=scale,
            recipient=self._recipient, return_address=self._return,
            include_return=self._include_return, airmail=self._airmail,
        )
        painter.end()


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

def _build_recipient_default(entry: ReportEntry) -> str:
    """Seed the recipient block from the report's station name + address."""
    lines: List[str] = []
    if entry.station_name.strip():
        lines.append(entry.station_name.strip())
    if entry.station_address.strip():
        lines.append(entry.station_address.strip())
    return "\n".join(lines)


def _build_return_default(profile: Optional[SenderProfile]) -> str:
    """Seed the return block from the active sender profile."""
    if profile is None:
        return ""
    if profile.postal_address.strip():
        text = profile.postal_address.strip()
        if profile.name.strip() and profile.name.strip() not in text.splitlines()[0]:
            return f"{profile.name.strip()}\n{text}"
        return text
    parts = [p for p in (profile.name.strip(), profile.location.strip()) if p]
    return "\n".join(parts)


class AirmailLabelDialog(QDialog):
    """Compose, preview, and print/save an airmail QSL label for a report."""

    def __init__(
        self,
        entry: ReportEntry,
        profile: Optional[SenderProfile] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Print Airmail QSL Label")
        self.resize(760, 560)
        self._entry = entry
        self._build_ui(entry, profile)
        self._refresh_preview()

    def _build_ui(
        self, entry: ReportEntry, profile: Optional[SenderProfile]
    ) -> None:
        outer = QHBoxLayout(self)

        # --- Left: editable fields ---
        left = QVBoxLayout()
        outer.addLayout(left, 0)

        form = QFormLayout()
        left.addLayout(form)

        self._size_combo = QComboBox()
        for label, _w, _h in LABEL_SIZES:
            self._size_combo.addItem(label)
        self._size_combo.currentIndexChanged.connect(self._refresh_preview)
        form.addRow("Label size:", self._size_combo)

        left.addWidget(QLabel("Recipient (station) address:"))
        self._recipient_edit = QTextEdit(_build_recipient_default(entry))
        self._recipient_edit.setFixedHeight(120)
        self._recipient_edit.textChanged.connect(self._refresh_preview)
        left.addWidget(self._recipient_edit)

        left.addWidget(QLabel("Return address:"))
        self._return_edit = QTextEdit(_build_return_default(profile))
        self._return_edit.setFixedHeight(110)
        self._return_edit.textChanged.connect(self._refresh_preview)
        left.addWidget(self._return_edit)

        self._include_return_cb = QCheckBox("Include return address")
        self._include_return_cb.setChecked(bool(self._return_edit.toPlainText().strip()))
        self._include_return_cb.stateChanged.connect(self._refresh_preview)
        left.addWidget(self._include_return_cb)

        self._airmail_cb = QCheckBox("Airmail border (PAR AVION)")
        self._airmail_cb.setChecked(True)
        self._airmail_cb.stateChanged.connect(self._refresh_preview)
        left.addWidget(self._airmail_cb)

        left.addStretch()

        btn_row = QHBoxLayout()
        left.addLayout(btn_row)
        print_btn = QPushButton("Print…")
        print_btn.setDefault(True)
        print_btn.clicked.connect(self._on_print)
        btn_row.addWidget(print_btn)
        pdf_btn = QPushButton("Save as PDF…")
        pdf_btn.clicked.connect(self._on_save_pdf)
        btn_row.addWidget(pdf_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)

        # --- Right: live preview ---
        right = QVBoxLayout()
        outer.addLayout(right, 1)
        right.addWidget(QLabel("Preview:"))
        self._preview = _LabelPreview()
        right.addWidget(self._preview, 1)

    # ------------------------------------------------------------------

    def _current_size(self) -> Tuple[float, float]:
        _label, w, h = LABEL_SIZES[self._size_combo.currentIndex()]
        return w, h

    def _refresh_preview(self) -> None:
        w_mm, h_mm = self._current_size()
        self._preview.set_params(
            w_mm, h_mm,
            self._recipient_edit.toPlainText(),
            self._return_edit.toPlainText(),
            self._include_return_cb.isChecked(),
            self._airmail_cb.isChecked(),
        )

    def _paint_to_printer(self, printer: QPrinter) -> None:
        w_mm, h_mm = self._current_size()
        painter = QPainter()
        if not painter.begin(printer):
            QMessageBox.critical(self, "Print Error", "Could not start the print job.")
            return
        try:
            dpi = printer.logicalDpiX() or 300
            px_per_mm = dpi / 25.4
            margin = 5.0 * px_per_mm
            rect = QRectF(margin, margin, w_mm * px_per_mm, h_mm * px_per_mm)
            paint_label(
                painter, rect, px_per_mm,
                recipient=self._recipient_edit.toPlainText(),
                return_address=self._return_edit.toPlainText(),
                include_return=self._include_return_cb.isChecked(),
                airmail=self._airmail_cb.isChecked(),
            )
        finally:
            painter.end()

    def _on_print(self) -> None:
        printer = QPrinter(QPrinter.HighResolution)
        dlg = QPrintDialog(printer, self)
        dlg.setWindowTitle("Print Airmail QSL Label")
        if dlg.exec_() == QPrintDialog.Accepted:
            self._paint_to_printer(printer)

    def _on_save_pdf(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Label as PDF", "airmail-label.pdf", "PDF Files (*.pdf)"
        )
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(path)
        self._paint_to_printer(printer)
        QMessageBox.information(self, "Saved", f"Label saved to:\n{path}")
