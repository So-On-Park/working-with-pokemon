"""A tiny info icon — a small subtle circle with an "i".

Drawn with a styled label (rounded background + ASCII "i") rather than a
Unicode glyph like ⓘ, which renders as tofu on fonts that lack it. The
explanation shows as a tooltip on HOVER."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

_ICON_PX = 13


class InfoIcon(QLabel):
    """Hover → shows `text` as a tooltip. Decorative, non-focusable."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__("i", parent)
        self._info = text
        self.setToolTip(text)
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
