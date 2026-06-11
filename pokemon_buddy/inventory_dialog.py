"""Inventory panel ('내 가방') — items the user has collected.

Four sections, one per ItemKind. Food / toy / pokeball are consumed
implicitly by feed / play / catch actions, so their tiles are display-only.
SPECIAL items (potions, stones, master ball) have a "사용" button on each
tile that emits `use_item_requested` upward to the app."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .config import COUNT_CAP
from .info_icon import InfoIcon
from .items import ItemDef, ItemKind, items_of
from .pokeball import make_pokeball_pixmap
from .sprites import get_item_sprite
from .state import Store


KIND_LABELS = {
    ItemKind.FOOD:     ("🍎 음식",        "밥주기에 사용"),
    ItemKind.TOY:      ("🎾 장난감",      "놀아주기에 사용"),
    ItemKind.POKEBALL: ("🔴 몬스터볼",    "야생 포켓몬 포획에 사용"),
    ItemKind.SPECIAL:  ("✨ 특수 아이템", "사용 버튼으로 활성화"),
    ItemKind.SKILL:    ("📜 기술 교본",   "전수 버튼으로 기술 전수"),
}

# Item kinds that get an action button on their tile (사용/전수).
_ACTION_KINDS = {ItemKind.SPECIAL, ItemKind.SKILL}

# Food / toy are shown as a SINGLE representative tile holding the kind's
# total count (밥주기/놀아주기 pick a random one each time, so individual
# variants don't need their own tiles).
_REP_ITEM = {
    ItemKind.FOOD: ItemDef("food", ItemKind.FOOD, "🍎", "음식",
                           description="밥주기에 쓰는 음식. 줄 때마다 랜덤으로 골라 줘요."),
    ItemKind.TOY:  ItemDef("toy", ItemKind.TOY, "🎾", "장난감",
                           description="놀아주기에 쓰는 장난감. 놀 때마다 랜덤으로 골라 줘요."),
}

# Heights vary by section so the SPECIAL tiles can fit a "사용" button.
TILE_W = 82
TILE_H_PLAIN = 84
TILE_H_SPECIAL = 104
ICON_PX = 36
_GRID_COLS = 4    # tiles per row (all sections share this for alignment)


def _load_item_pixmap(item: ItemDef, side: int) -> Optional[QPixmap]:
    """Resolve an item to a QPixmap. Pokeballs use the painted icon; SPECIAL
    items load from disk (downloading lazily on first call); anything else
    has no sprite and the caller falls back to the emoji glyph."""
    if item.kind == ItemKind.POKEBALL:
        return make_pokeball_pixmap(side)
    if not item.slug:
        return None
    path = get_item_sprite(item.slug)
    if path is None:
        return None
    pm = QPixmap(str(Path(path)))
    if pm.isNull():
        return None
    return pm.scaled(side, side, Qt.KeepAspectRatio,
                     Qt.SmoothTransformation)


def _dim_pixmap(pm: QPixmap) -> QPixmap:
    """Render `pm` desaturated by overlaying a translucent gray — used for
    item tiles with count 0 so the icon still hints at what's there."""
    out = QPixmap(pm.size())
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setOpacity(0.35)
    p.drawPixmap(0, 0, pm)
    p.end()
    return out


class _ItemTile(QFrame):
    use_clicked = Signal(str)     # item_key — 사용/전수
    export_clicked = Signal(str)  # item_key — 보내기 (skill scrolls only)

    def __init__(self, item: ItemDef, count: int,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.item = item
        owned = count > 0
        height = TILE_H_SPECIAL if item.kind in _ACTION_KINDS else TILE_H_PLAIN
        self.setFixedSize(TILE_W, height)
        self.setFrameShape(QFrame.StyledPanel)

        if item.kind in _ACTION_KINDS and owned:
            border = "#a380e8"
            bg = "#f6f2ff"
        else:
            border = "#bbb" if owned else "#e0e0e0"
            bg = "#ffffff" if owned else "#fafafa"
        self.setStyleSheet(
            f"_ItemTile {{ background: {bg}; border: 1px solid {border};"
            f"  border-radius: 6px; }}"
        )

        col = QVBoxLayout(self)
        col.setContinuousMargin = None  # noqa: pyflakes — silence editor
        col.setContentsMargins(3, 3, 3, 3)
        col.setSpacing(0)

        # Icon — pokeball/sprite if available, else emoji glyph fallback.
        icon = QLabel()
        icon.setAlignment(Qt.AlignCenter)
        # A touch more room + a slightly smaller emoji so the glyph isn't
        # clipped on any edge.
        icon.setFixedHeight(ICON_PX + 12)
        pm = _load_item_pixmap(item, ICON_PX)
        if pm is not None:
            icon.setPixmap(_dim_pixmap(pm) if not owned else pm)
        else:
            icon.setText(item.emoji)
            f = QFont(); f.setPointSize(16)
            icon.setFont(f)
            if not owned:
                icon.setStyleSheet("color: #aaa;")
        col.addWidget(icon)

        label = QLabel(item.label)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(
            f"font-size: 8pt; color: {'#222' if owned else '#aaa'};"
        )
        label.setWordWrap(True)
        col.addWidget(label)

        count_row = QLabel(f"×{min(count, COUNT_CAP)}" if owned else "—")
        count_row.setAlignment(Qt.AlignCenter)
        count_row.setStyleSheet(
            f"font-size: 8pt; color: {'#4a7ddc' if owned else '#bbb'};"
            "font-weight: bold;"
        )
        col.addWidget(count_row)

        # Action button — SPECIAL (사용), SKILL (전수 + 보내기).
        if item.kind in _ACTION_KINDS:
            use_style = (
                "QPushButton {"
                "  background: #6f4cd6; color: white;"
                "  border: none; border-radius: 4px;"
                "  font-size: 7pt; padding: 0px;"
                "}"
                "QPushButton:hover { background: #5d3fc0; }"
                "QPushButton:disabled { background: #ccc; color: #888; }"
            )
            send_style = (
                "QPushButton {"
                "  background: #e8553e; color: white;"
                "  border: none; border-radius: 4px;"
                "  font-size: 7pt; padding: 0px;"
                "}"
                "QPushButton:hover { background: #cf4631; }"
                "QPushButton:disabled { background: #ccc; color: #888; }"
            )
            use_btn = QPushButton("전수" if item.kind == ItemKind.SKILL else "사용")
            use_btn.setEnabled(owned)
            use_btn.setFixedHeight(18)
            use_btn.setStyleSheet(use_style)
            use_btn.clicked.connect(lambda: self.use_clicked.emit(self.item.key))
            if item.kind == ItemKind.SKILL:
                # Skill scrolls can also be sent to a file.
                send_btn = QPushButton("보내기")
                send_btn.setEnabled(owned)
                send_btn.setFixedHeight(18)
                send_btn.setStyleSheet(send_style)
                send_btn.clicked.connect(
                    lambda: self.export_clicked.emit(self.item.key))
                brow = QHBoxLayout()
                brow.setContentsMargins(0, 0, 0, 0)
                brow.setSpacing(2)
                brow.addWidget(use_btn)
                brow.addWidget(send_btn)
                col.addLayout(brow)
            else:
                col.addWidget(use_btn)

        # Per-item explanation simply on hover — set the tooltip on the tile
        # and its labels (icon / name / count) so pointing at the item shows
        # what it does. No extra icon needed.
        if item.description:
            self.setToolTip(item.description)
            for lbl in self.findChildren(QLabel):
                lbl.setToolTip(item.description)


class InventoryPanel(QWidget):
    """Compact 'my bag' tab — four sections (food / toy / pokeball / special).
    Emits `use_item_requested(item_key)` when the user clicks a SPECIAL tile's
    사용 button. MainPanel forwards this up to the app."""

    use_item_requested = Signal(str)
    export_skill_requested = Signal(str)  # skill item_key → 보내기

    def __init__(self, store: Store, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(4, 2, 4, 2)
        self._root.setSpacing(6)

        self._summary = QLabel("")
        sf = QFont(); sf.setBold(True); sf.setPointSize(10)
        self._summary.setFont(sf)
        self._summary.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._root.addWidget(self._summary)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._root.addWidget(self._scroll, stretch=1)

        self._build_content()

    def _build_content(self) -> None:
        # Update summary. Counts are shown capped at COUNT_CAP so a kind never
        # reads as an absurd number.
        totals = {kind: min(self.store.total_of_kind(kind.value), COUNT_CAP)
                  for kind in ItemKind}
        self._summary.setText(
            f"음식 {totals[ItemKind.FOOD]}  ·  "
            f"장난감 {totals[ItemKind.TOY]}  ·  "
            f"몬스터볼 {totals[ItemKind.POKEBALL]}  ·  "
            f"특수 {totals[ItemKind.SPECIAL]}  ·  "
            f"교본 {totals[ItemKind.SKILL]}"
        )

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(6)
        inner_layout.setContentsMargins(2, 2, 2, 2)

        def _header(title: str, hint: str) -> QWidget:
            head_w = QWidget()
            row = QHBoxLayout(head_w)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(5)
            head = QLabel(title)
            hf = QFont(); hf.setBold(True); hf.setPointSize(10)
            head.setFont(hf)
            head.setStyleSheet("padding-left: 2px;")  # don't clip leading emoji
            row.addWidget(head)
            row.addWidget(InfoIcon(hint))
            row.addStretch(1)
            return head_w

        # ---- 기본 아이템: 음식 / 장난감 / 몬스터볼 in ONE row ----
        inner_layout.addWidget(_header(
            "🎒 기본 아이템",
            "밥주기·놀아주기·포획에 쓰는 기본 아이템. 음식/장난감은 줄 때마다 "
            "랜덤으로 골라 줘요."))
        _AL = Qt.AlignLeft | Qt.AlignTop

        def _new_grid() -> QGridLayout:
            g = QGridLayout()
            g.setSpacing(4)
            g.setContentsMargins(0, 0, 0, 4)
            # 4 equal-width columns inside the fixed-width holder → identical
            # column positions in every section (no per-section drift).
            for c in range(_GRID_COLS):
                g.setColumnStretch(c, 1)
            return g

        grid_w = _GRID_COLS * TILE_W + (_GRID_COLS - 1) * 4

        def _add_centered(grid: QGridLayout) -> None:
            # Fixed-width holder so every section lines up identically and the
            # block sits centered with equal padding on both sides.
            holder = QWidget()
            holder.setFixedWidth(grid_w)
            holder.setLayout(grid)
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addStretch(1)
            row.addWidget(holder)
            row.addStretch(1)
            inner_layout.addLayout(row)

        basic = _new_grid()
        basic.addWidget(_ItemTile(_REP_ITEM[ItemKind.FOOD],
                                  totals[ItemKind.FOOD]), 0, 0, _AL)
        basic.addWidget(_ItemTile(_REP_ITEM[ItemKind.TOY],
                                  totals[ItemKind.TOY]), 0, 1, _AL)
        pballs = items_of(ItemKind.POKEBALL)
        if pballs:
            basic.addWidget(_ItemTile(pballs[0],
                                      totals[ItemKind.POKEBALL]), 0, 2, _AL)
        _add_centered(basic)

        # ---- 특수 아이템 / 기술 교본 — own sections (multiple tiles) ----
        for kind in [ItemKind.SPECIAL, ItemKind.SKILL]:
            title, hint = KIND_LABELS[kind]
            inner_layout.addWidget(_header(title, hint))
            grid = _new_grid()
            for i, item in enumerate(items_of(kind)):
                count = self.store.get_item_count(item.key)
                tile = _ItemTile(item, count)
                tile.use_clicked.connect(self.use_item_requested)
                if kind == ItemKind.SKILL:
                    tile.export_clicked.connect(self.export_skill_requested)
                grid.addWidget(tile, i // _GRID_COLS, i % _GRID_COLS, _AL)
            _add_centered(grid)

        inner_layout.addStretch(1)
        self._scroll.setWidget(inner)

    def refresh(self) -> None:
        """Rebuild the entire panel from current Store counts. Called by
        MainPanel after the app processes a use_item action."""
        self._build_content()

    def cleanup(self) -> None:
        pass
