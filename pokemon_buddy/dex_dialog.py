"""Pokedex panel — read-only encyclopedia. Single grid (no inner tabs):
all 151 base entries plus rare cards inlined right after their normal
counterpart once caught. Hosted as one tab inside MainPanel."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .animated_sprite import AnimatedSprite
from .config import BULK_DEX_RANGE, DIALOG_W, SHINY_LABEL
from .pokemon_names import fallback_name, get_name_cached
from .sprites import get_buddy_sprite_with_fallback
from .state import Store


COLS = 4
SPRITE_PX = 56
GRID_SPACING = 4

# Card width is derived from DIALOG_W so the grid exactly fills the panel.
# Everything that eats horizontal space has to be accounted for, or the
# right-hand column gets clipped — which is what happened when the vertical
# scrollbar (the dex always has one: 151+ entries) wasn't subtracted.
_MAIN_PANEL_MARGINS = 8 + 8      # MainPanel root
_DEX_PANEL_MARGINS = 4 + 4       # DexPanel root
_GRID_MARGINS = 2 + 2            # QGridLayout inside the scroll area
_SCROLLBAR_W = 18                # vertical scrollbar, always shown
_CONTENT_W = DIALOG_W - (
    _MAIN_PANEL_MARGINS + _DEX_PANEL_MARGINS + _GRID_MARGINS + _SCROLLBAR_W
)
CARD_W = (_CONTENT_W - (COLS - 1) * GRID_SPACING) // COLS
CARD_H = 100


class _DexCard(QFrame):
    def __init__(self, dex_id: int, sprite_style: str, store: Store,
                 is_rare: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.dex_id = dex_id
        self.is_rare = is_rare
        self.setFixedSize(CARD_W, CARD_H)
        self.setFrameShape(QFrame.StyledPanel)

        caught = store.get_dex_entry(dex_id, is_rare=is_rare)
        caught_count = caught.count if caught else 0
        is_caught = caught is not None

        if is_caught:
            border = "#e6b14a" if is_rare else "#bbb"
            bg = "#fff8e8" if is_rare else "#ffffff"
        else:
            border = "#ccc"
            bg = "#f5f5f5"

        self.setStyleSheet(
            f"_DexCard {{"
            f"  background: {bg};"
            f"  border: 1px solid {border};"
            f"  border-radius: 6px;"
            f"}}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(1)

        sprite_path = get_buddy_sprite_with_fallback(sprite_style, dex_id,
                                                    is_rare)
        self.sprite = AnimatedSprite(
            Path(sprite_path) if sprite_path else None,
            SPRITE_PX,
            silhouette=not is_caught,
            parent=self,
        )
        sprite_row = QHBoxLayout()
        sprite_row.setContentsMargins(0, 0, 0, 0)
        sprite_row.addStretch(1)
        sprite_row.addWidget(self.sprite)
        sprite_row.addStretch(1)
        layout.addLayout(sprite_row)

        num_text = f"#{dex_id:04d}"
        if is_rare:
            num_text = f"✨ {num_text}"
        num = QLabel(num_text)
        num.setAlignment(Qt.AlignCenter)
        num.setStyleSheet("color: #888; font-size: 7pt;")
        layout.addWidget(num)

        if is_caught:
            base = (caught.name if caught.name and not caught.name.startswith("#")
                    else (get_name_cached(dex_id) or fallback_name(dex_id)))
            # 이로치 keeps the plain species name — the ✨ on the dex number
            # above is what tells the two entries apart.
            display = base
            if caught_count > 1:
                display = f"{display} ×{caught_count}"
            color = "#c47b1c" if is_rare else "#222"
            name_label = QLabel(display)
            name_label.setAlignment(Qt.AlignCenter)
            name_label.setStyleSheet(
                f"font-weight: bold; font-size: 8pt; color: {color};"
            )
            if is_rare:
                name_label.setToolTip(f"✨ {SHINY_LABEL} — 색이 다른 희귀 개체")
            layout.addWidget(name_label)
        else:
            unknown = QLabel("???")
            unknown.setAlignment(Qt.AlignCenter)
            unknown.setStyleSheet("color: #aaa; font-size: 8pt;")
            layout.addWidget(unknown)


class DexPanel(QWidget):
    """Read-only encyclopedia tab. No actions, no signals — pure browse."""

    def __init__(self, store: Store, sprite_style: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sprites: list[AnimatedSprite] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 2, 4, 2)
        root.setSpacing(4)

        from . import custom_pokemon
        custom_ids = custom_pokemon.list_dex_ids()

        all_entries = store.list_dex()
        # Split caught entries: vanilla in-range vs custom for the summary.
        lo, hi = BULK_DEX_RANGE
        custom_set = set(custom_ids)
        vanilla_normal_caught = sum(
            1 for e in all_entries
            if not e.is_rare and lo <= e.dex_id <= hi
        )
        rare_caught = sum(1 for e in all_entries if e.is_rare)
        custom_caught = sum(
            1 for e in all_entries
            if not e.is_rare and e.dex_id in custom_set
        )
        total = hi - lo + 1
        summary_text = f"{vanilla_normal_caught}/{total}"
        if rare_caught:
            summary_text += f"  ·  ✨ {rare_caught}"
        if custom_ids:
            summary_text += f"  ·  커스텀 {custom_caught}/{len(custom_ids)}"
        summary = QLabel(summary_text)
        sf = QFont(); sf.setBold(True); sf.setPointSize(10)
        summary.setFont(sf)
        summary.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        root.addWidget(summary)

        rare_ids = {e.dex_id for e in all_entries if e.is_rare}

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        grid = QGridLayout(inner)
        # Must match the value CARD_W was derived from.
        grid.setSpacing(GRID_SPACING)
        grid.setContentsMargins(2, 2, 2, 2)

        slot = 0
        for dex_id in range(lo, hi + 1):
            r, c = divmod(slot, COLS)
            card = _DexCard(dex_id, sprite_style, store,
                            is_rare=False, parent=inner)
            grid.addWidget(card, r, c)
            self._sprites.append(card.sprite)
            slot += 1
            if dex_id in rare_ids:
                r, c = divmod(slot, COLS)
                card = _DexCard(dex_id, sprite_style, store,
                                is_rare=True, parent=inner)
                grid.addWidget(card, r, c)
                self._sprites.append(card.sprite)
                slot += 1

        # Custom (user-registered) pokemon land at the tail end of the grid.
        # No rare variants exist for them.
        for dex_id in custom_ids:
            r, c = divmod(slot, COLS)
            card = _DexCard(dex_id, sprite_style, store,
                            is_rare=False, parent=inner)
            grid.addWidget(card, r, c)
            self._sprites.append(card.sprite)
            slot += 1

        scroll.setWidget(inner)
        root.addWidget(scroll, stretch=1)

    def cleanup(self) -> None:
        for s in self._sprites:
            s.stop()
        self._sprites.clear()
