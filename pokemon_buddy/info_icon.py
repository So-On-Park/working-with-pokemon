"""A tiny ⓘ info icon.

Keeps panels uncluttered: instead of printing a long explanation next to
every item, we show a small circled-i. Hovering it surfaces the text as a
tooltip; clicking it pops the same tooltip immediately (handy on touch or
when the hover delay feels slow)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QToolTip, QWidget


class InfoIcon(QLabel):
    """Hover or click → shows `text` as a tooltip. Decorative, non-focusable."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__("ⓘ", parent)
        self._info = text
        self.setToolTip(text)
        self.setCursor(Qt.PointingHandCursor)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            "QLabel { color: #4a7ddc; font-size: 10pt; }"
            "QLabel:hover { color: #2f5bb7; }"
        )

    def set_info(self, text: str) -> None:
        self._info = text
        self.setToolTip(text)

    def mousePressEvent(self, ev) -> None:  # noqa: N802
        QToolTip.showText(ev.globalPosition().toPoint(), self._info, self)
        ev.accept()
