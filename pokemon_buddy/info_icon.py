"""A tiny info icon — a small blue circle with an "i".

Drawn with a styled label (rounded background + ASCII "i") rather than a
Unicode glyph like ⓘ, which renders as tofu on fonts that lack it. Hovering
it surfaces the text as a tooltip; clicking pops the same tooltip immediately
(handy on touch, or when the hover delay feels slow)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QToolTip, QWidget

_ICON_PX = 13


class InfoIcon(QLabel):
    """Hover or click → shows `text` as a tooltip. Decorative, non-focusable."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__("i", parent)
        self._info = text
        self.setToolTip(text)
        self.setCursor(Qt.PointingHandCursor)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(_ICON_PX, _ICON_PX)
        # Subtle: muted gray, not an attention-grabbing blue.
        self.setStyleSheet(
            "QLabel {"
            "  background: #e2e2e2; color: #777;"
            f"  border-radius: {_ICON_PX // 2}px;"
            "  font-weight: bold; font-style: italic;"
            "  font-family: 'Segoe UI', Arial, sans-serif; font-size: 7pt;"
            "}"
            "QLabel:hover { background: #cfcfcf; color: #555; }"
        )

    def set_info(self, text: str) -> None:
        self._info = text
        self.setToolTip(text)

    def mousePressEvent(self, ev) -> None:  # noqa: N802
        QToolTip.showText(ev.globalPosition().toPoint(), self._info, self)
        ev.accept()
