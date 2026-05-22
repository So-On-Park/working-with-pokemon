"""Animated popup that replaces the buddy's right-click context menu.

Layout (top to bottom):
  - Header   : name + level pill
  - Species  : species label (with 레어 prefix if applicable)
  - Hearts   : 친밀도 hearts + numeric value
  - EXP gauge: single bar (hunger/happiness are gone in v2)
  - Actions  : feed / play / train / bag / dex / rename / close

Show animation: scale-up + fade-in from 92% → 100% over 180ms (OutBack easing).
Closes automatically on any click outside (Qt.Popup flag does this for us)."""

from __future__ import annotations

from typing import Callable, List, Tuple

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .stat_gauge import StatGauge
from .state import Buddy


# Action keys exposed via the `action` signal — app.py routes them.
ACTION_FEED = "feed"
ACTION_PLAY = "play"
ACTION_TRAIN = "train"
ACTION_BAG = "bag"            # 내 포켓몬
ACTION_INVENTORY = "inventory"  # 내 가방 (items)
ACTION_DEX = "dex"
ACTION_RENAME = "rename"
ACTION_DETAIL = "detail"        # 상세 정보 (PokemonDetailDialog)


class BuddyMenuPopup(QWidget):
    """Frameless animated popup. Emits `action(str)` for the chosen button."""

    action = Signal(str)

    POPUP_W = 240
    POPUP_H = 178

    # Two rows of four — actions on top, navigation on bottom.
    ACTION_ROW: List[Tuple[str, str, str]] = [
        (ACTION_FEED,   "🍎", "밥 주기"),
        (ACTION_PLAY,   "🎯", "놀아주기"),
        (ACTION_TRAIN,  "💪", "훈련"),
        (ACTION_RENAME, "✏️", "이름 변경"),
    ]
    NAV_ROW: List[Tuple[str, str, str]] = [
        (ACTION_BAG,       "🐾", "내 포켓몬"),
        (ACTION_INVENTORY, "🎒", "내 가방"),
        (ACTION_DEX,       "📖", "도감"),
        (ACTION_DETAIL,    "📋", "상세 정보"),
    ]

    def __init__(self, buddy: Buddy, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.Popup
            | Qt.FramelessWindowHint
            | Qt.NoDropShadowWindowHint
            | Qt.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        # Auto-destroy on close so a stale popup never lingers and steals
        # mouse grab from the next one (the bug with 2+ buddies out).
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setFixedSize(self.POPUP_W, self.POPUP_H)

        card = QWidget(self)
        card.setObjectName("card")
        card.setStyleSheet(
            "#card {"
            "  background: rgba(255,255,255,238);"
            "  border: 1px solid rgba(60,60,60,140);"
            "  border-radius: 12px;"
            "}"
        )
        margin = 10
        card.setGeometry(margin, margin,
                         self.POPUP_W - 2 * margin,
                         self.POPUP_H - 2 * margin)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(22)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 110))
        card.setGraphicsEffect(shadow)

        root = QVBoxLayout(card)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(6)

        # Header — display name (nickname) + species inline + level pill.
        # When there's a nickname (or the buddy is rare) the species label
        # sits right next to the name in smaller, muted text, instead of on
        # its own line below.
        header_row = QHBoxLayout()
        header_row.setSpacing(6)

        name_label = QLabel(buddy.display_name)
        name_font = QFont()
        name_font.setBold(True)
        name_font.setPointSize(12)
        name_label.setFont(name_font)
        name_label.setStyleSheet("color: #222;")
        header_row.addWidget(name_label)

        if buddy.nickname or buddy.is_rare:
            species_color = "#c47b1c" if buddy.is_rare else "#888"
            species_label = QLabel(buddy.species_label)
            species_label.setStyleSheet(
                f"color: {species_color}; font-size: 9pt;"
            )
            header_row.addWidget(species_label)

        header_row.addStretch(1)

        lvl_label = QLabel(f"Lv. {buddy.level}")
        lvl_font = QFont()
        lvl_font.setBold(True)
        lvl_font.setPointSize(10)
        lvl_label.setFont(lvl_font)
        lvl_label.setStyleSheet(
            "color: white; background: #4a7ddc;"
            "border-radius: 8px; padding: 1px 8px;"
        )
        header_row.addWidget(lvl_label)
        root.addLayout(header_row)

        # Friendship — hearts + value. The hidden XP accumulator and the
        # personality are NOT shown here — those live in the bag detail
        # dialog so the popup stays focused on quick actions.
        hearts = "❤️" * buddy.hearts + "♡" * (5 - buddy.hearts)
        hearts_label = QLabel(f"{hearts}  친밀도 {buddy.friendship}/100")
        hearts_label.setStyleSheet("color: #a04060; font-size: 9pt;")
        root.addWidget(hearts_label)

        # Single gauge — EXP only.
        root.addWidget(StatGauge("EXP", buddy.exp, buddy.exp_to_next,
                                 QColor("#4a7ddc")))

        # Action buttons — two rows.
        for row_defs in (self.ACTION_ROW, self.NAV_ROW):
            btn_row = QHBoxLayout()
            btn_row.setSpacing(4)
            btn_row.setContentsMargins(0, 3, 0, 0)
            for key, emoji, tip in row_defs:
                btn = QPushButton(emoji)
                btn.setToolTip(tip)
                btn.setFixedHeight(28)
                btn.setStyleSheet(
                    "QPushButton {"
                    "  background: #f5f5f5;"
                    "  border: 1px solid #ccc;"
                    "  border-radius: 5px;"
                    "  font-size: 11pt;"
                    "}"
                    "QPushButton:hover { background: #e8e8e8; }"
                    "QPushButton:pressed { background: #d0d0d0; }"
                )
                btn.clicked.connect(self._make_handler(key))
                btn_row.addWidget(btn, stretch=1)
            root.addLayout(btn_row)

        # Show animation state
        self._geom_anim = QPropertyAnimation(self, b"geometry")
        self._geom_anim.setDuration(180)
        self._geom_anim.setEasingCurve(QEasingCurve.OutBack)

        self._opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self._opacity_anim.setDuration(160)

    # ---- click handlers ----
    def _make_handler(self, key: str) -> Callable[[], None]:
        def handler() -> None:
            self.action.emit(key)
            self.close()
        return handler

    # ---- placement + show ----
    def show_animated(self, anchor_global: QRect) -> None:
        from PySide6.QtGui import QGuiApplication
        # Use the screen containing the buddy, not the primary screen — the
        # popup would otherwise land on monitor #1 even when the buddy is on
        # a secondary monitor.
        anchor_center = anchor_global.center()
        screen_obj = (QGuiApplication.screenAt(anchor_center)
                      or QGuiApplication.primaryScreen())
        screen = screen_obj.availableGeometry()

        cx = anchor_center.x()
        x = max(screen.left() + 8, min(cx - self.POPUP_W // 2,
                                       screen.right() - self.POPUP_W - 8))

        gap = 8
        y_above = anchor_global.top() - self.POPUP_H - gap
        y_below = anchor_global.bottom() + gap
        if y_above >= screen.top() + 8:
            y = y_above
        else:
            y = min(y_below, screen.bottom() - self.POPUP_H - 8)

        final = QRect(x, y, self.POPUP_W, self.POPUP_H)
        shrink = 14
        start = QRect(
            final.x() + shrink, final.y() + shrink,
            final.width() - 2 * shrink, final.height() - 2 * shrink,
        )

        self.setGeometry(start)
        self.setWindowOpacity(0.0)
        self.show()

        self._geom_anim.stop()
        self._geom_anim.setStartValue(start)
        self._geom_anim.setEndValue(final)
        self._geom_anim.start()

        self._opacity_anim.stop()
        self._opacity_anim.setStartValue(0.0)
        self._opacity_anim.setEndValue(1.0)
        self._opacity_anim.start()
