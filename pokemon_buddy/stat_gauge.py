"""Tiny custom-painted progress bar used in the buddy popup."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


class StatGauge(QWidget):
    def __init__(self, label: str, value: int, max_value: int,
                 fill_color: QColor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label = label
        self._value = max(0, min(int(value), int(max_value)))
        self._max = max(1, int(max_value))
        self._fill = QColor(fill_color)
        self.setFixedHeight(20)

    # --- API ---
    def set_value(self, value: int, max_value: int | None = None) -> None:
        if max_value is not None:
            self._max = max(1, int(max_value))
        self._value = max(0, min(int(value), self._max))
        self.update()

    # --- paint ---
    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        # Layout: [label 28%] [bar 50%] [value 22%]
        w = self.width()
        h = self.height()
        label_w = int(w * 0.30)
        value_w = int(w * 0.22)
        bar_x = label_w + 6
        bar_w = w - label_w - value_w - 12
        bar_h = 8
        bar_y = (h - bar_h) / 2

        font = QFont()
        font.setPointSize(9)
        p.setFont(font)

        # Label
        p.setPen(QColor(60, 60, 60))
        p.drawText(QRectF(0, 0, label_w, h), Qt.AlignVCenter | Qt.AlignLeft,
                   self._label)

        # Bar background
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(225, 225, 225))
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 4, 4)

        # Fill
        ratio = self._value / self._max
        fill_w = max(0.0, bar_w * ratio)
        if fill_w > 0:
            p.setBrush(self._fill)
            p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 4, 4)

        # Value text
        p.setPen(QColor(60, 60, 60))
        p.drawText(
            QRectF(bar_x + bar_w + 4, 0, value_w, h),
            Qt.AlignVCenter | Qt.AlignLeft,
            f"{self._value}/{self._max}",
        )
        p.end()
