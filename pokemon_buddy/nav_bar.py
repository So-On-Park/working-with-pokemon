"""Top navigation strip shared by every dialog (bag / inventory / dex /
reminders). The user can hop between tabs within a single MainPanel window
without ever closing it — clicking a tab emits `nav(key)`."""

from __future__ import annotations

from typing import List, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QWidget,
)


# Tab identifier keys used as routing tags.
NAV_POKEMON   = "pokemon"     # BagPanel ("내 포켓몬")
NAV_INVENTORY = "inventory"   # InventoryPanel ("내 가방")
NAV_DEX       = "dex"
NAV_REMINDERS = "reminders"
NAV_SCHEDULE  = "schedule"    # DailySchedulePanel — wall-clock 출근/점심/퇴근


# (key, emoji, label) for the entries. Order = left-to-right display.
_NAV_ITEMS: List[Tuple[str, str, str]] = [
    (NAV_INVENTORY, "🎒", "내 가방"),
    (NAV_POKEMON,   "🐾", "내 포켓몬"),
    (NAV_DEX,       "📖", "도감"),
    (NAV_REMINDERS, "⏰", "리마인더"),
    (NAV_SCHEDULE,  "📅", "일정"),
]


class NavBar(QFrame):
    """Tab-strip that highlights the current tab. `set_current(key)` updates
    which tab looks selected — used by MainPanel when switching the
    underlying QStackedWidget so the strip stays in sync."""

    nav = Signal(str)

    def __init__(self, current: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.setFixedHeight(36)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Track each button alongside its key so set_current can update style.
        # Icon-only: the emoji IS the button. Label lives in the tooltip so
        # hovering still tells the user which tab is which.
        self._buttons: List[Tuple[str, QPushButton]] = []
        for key, emoji, label in _NAV_ITEMS:
            btn = QPushButton(emoji)
            btn.setToolTip(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(30)
            btn.clicked.connect(self._handler(key))
            self._buttons.append((key, btn))
            layout.addWidget(btn, stretch=1)

        self.set_current(current)

    def set_current(self, current: str) -> None:
        """Refresh which tab looks selected. Each button is enabled only when
        it's NOT the current tab (so clicking it again is a no-op)."""
        for key, btn in self._buttons:
            is_current = (key == current)
            btn.setEnabled(not is_current)
            # Larger glyph size since the emoji is the only visible content.
            font = QFont(); font.setPointSize(13)
            btn.setFont(font)
            btn.setStyleSheet(self._style_for(is_current))

    @staticmethod
    def _style_for(is_current: bool) -> str:
        if is_current:
            return (
                "QPushButton {"
                "  background: #4a7ddc; color: white;"
                "  border: 1px solid #3a6ac0;"
                "  border-radius: 6px; padding: 2px 4px;"
                "}"
                "QPushButton:disabled { color: white; background: #4a7ddc; }"
            )
        return (
            "QPushButton {"
            "  background: #f7f7f7; color: #333;"
            "  border: 1px solid #cfcfcf;"
            "  border-radius: 6px; padding: 2px 4px;"
            "}"
            "QPushButton:hover { background: #ececec; }"
        )

    def _handler(self, key: str):
        def _go() -> None:
            self.nav.emit(key)
        return _go
