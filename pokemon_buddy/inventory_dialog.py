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
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .items import ItemDef, ItemKind, items_of
from .pokeball import make_pokeball_pixmap
from .sprites import get_item_sprite
from .state import Store


KIND_LABELS = {
    ItemKind.FOOD:     ("🍎 음식",        "밥주기에 사용"),
    ItemKind.TOY:      ("🎾 장난감",      "놀아주기에 사용"),
    ItemKind.POKEBALL: ("🔴 몬스터볼",    "야생 포켓몬 포획에 사용"),
    ItemKind.SPECIAL:  ("✨ 특수 아이템", "사용 버튼으로 활성화"),
}

# Heights vary by section so the SPECIAL tiles can fit a "사용" button.
TILE_W = 82
TILE_H_PLAIN = 76
TILE_H_SPECIAL = 100
ICON_PX = 36


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
    use_clicked = Signal(str)  # item_key

    def __init__(self, item: ItemDef, count: int,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.item = item
        owned = count > 0
        height = TILE_H_SPECIAL if item.kind == ItemKind.SPECIAL else TILE_H_PLAIN
        self.setFixedSize(TILE_W, height)
        self.setFrameShape(QFrame.StyledPanel)

        if item.kind == ItemKind.SPECIAL and owned:
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
        icon.setFixedHeight(ICON_PX + 4)
        pm = _load_item_pixmap(item, ICON_PX)
        if pm is not None:
            icon.setPixmap(_dim_pixmap(pm) if not owned else pm)
        else:
            icon.setText(item.emoji)
            f = QFont(); f.setPointSize(18)
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

        count_row = QLabel(f"×{count}" if owned else "—")
        count_row.setAlignment(Qt.AlignCenter)
        count_row.setStyleSheet(
            f"font-size: 8pt; color: {'#4a7ddc' if owned else '#bbb'};"
            "font-weight: bold;"
        )
        col.addWidget(count_row)

        # Use button — SPECIAL items only.
        if item.kind == ItemKind.SPECIAL:
            btn = QPushButton("사용")
            btn.setEnabled(owned)
            btn.setFixedHeight(18)
            btn.setStyleSheet(
                "QPushButton {"
                "  background: #6f4cd6; color: white;"
                "  border: none; border-radius: 4px;"
                "  font-size: 8pt; padding: 0px;"
                "}"
                "QPushButton:hover { background: #5d3fc0; }"
                "QPushButton:disabled { background: #ccc; color: #888; }"
            )
            btn.clicked.connect(lambda: self.use_clicked.emit(self.item.key))
            col.addWidget(btn)


class InventoryPanel(QWidget):
    """Compact 'my bag' tab — four sections (food / toy / pokeball / special).
    Emits `use_item_requested(item_key)` when the user clicks a SPECIAL tile's
    사용 button. MainPanel forwards this up to the app."""

    use_item_requested = Signal(str)

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
        # Update summary
        totals = {kind: self.store.total_of_kind(kind.value)
                  for kind in ItemKind}
        self._summary.setText(
            f"음식 {totals[ItemKind.FOOD]}  ·  "
            f"장난감 {totals[ItemKind.TOY]}  ·  "
            f"몬스터볼 {totals[ItemKind.POKEBALL]}  ·  "
            f"특수 {totals[ItemKind.SPECIAL]}"
        )

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(6)
        inner_layout.setContentsMargins(2, 2, 2, 2)

        for kind in [ItemKind.FOOD, ItemKind.TOY,
                     ItemKind.POKEBALL, ItemKind.SPECIAL]:
            title, hint = KIND_LABELS[kind]
            head = QLabel(f"{title}   <span style='color:#888'>{hint}</span>")
            head.setTextFormat(Qt.RichText)
            head_font = QFont(); head_font.setBold(True); head_font.setPointSize(10)
            head.setFont(head_font)
            inner_layout.addWidget(head)

            grid = QGridLayout()
            grid.setSpacing(4)
            grid.setContentsMargins(0, 0, 0, 4)
            for i, item in enumerate(items_of(kind)):
                count = self.store.get_item_count(item.key)
                tile = _ItemTile(item, count)
                if kind == ItemKind.SPECIAL:
                    tile.use_clicked.connect(self.use_item_requested)
                grid.addWidget(tile, i // 4, i % 4)
            inner_layout.addLayout(grid)

        inner_layout.addStretch(1)
        self._scroll.setWidget(inner)

    def refresh(self) -> None:
        """Rebuild the entire panel from current Store counts. Called by
        MainPanel after the app processes a use_item action."""
        self._build_content()

    def cleanup(self) -> None:
        pass
