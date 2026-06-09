"""A tiny info icon — a small blue circle with an "i".

Drawn with a styled label (rounded background + ASCII "i") rather than a
Unicode glyph like ⓘ, which renders as tofu on fonts that lack it. Hovering
it surfaces the text as a tooltip; clicking pops the same tooltip immediately
(handy on touch, or when the hover delay feels slow)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QToolTip, QWidget

_ICON_PX = 16


class InfoIcon(QLabel):
    """Hover or click → shows `text` as a tooltip. Decorative, non-focusable."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__("i", parent)
        self._info = text
        self.setToolTip(text)
        self.setCursor(Qt.PointingHandCursor)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(_ICON_PX, _ICON_PX)
        self.setStyleSheet(
            "QLabel {"
            "  background: #4a7ddc; color: white;"
            f"  border-radius: {_ICON_PX // 2}px;"
            "  font-weight: bold; font-style: italic;"
            "  font-family: 'Segoe UI', Arial, sans-serif; font-size: 9pt;"
            "}"
            "QLabel:hover { background: #2f5bb7; }"
        )

    def set_info(self, text: str) -> None:
        self._info = text
        self.setToolTip(text)

    def mousePressEvent(self, ev) -> None:  # noqa: N802
        QToolTip.showText(ev.globalPosition().toPoint(), self._info, self)
        ev.accept()
