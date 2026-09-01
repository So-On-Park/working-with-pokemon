"""Bag panel — every Pokemon you currently own as a distinct individual.

Compact horizontal cards: sprite | text | icon buttons. The buttons are
icon-only (⭐ party, 📋 detail, ✏️ rename, 📮 박사에게 보내기).
Hosted inside `MainPanel` as one of four tabs."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .animated_sprite import AnimatedSprite
from .pokeball import make_pokeball_pixmap
from .sprites import get_buddy_sprite_with_fallback, get_item_sprite
from .state import Buddy, Store


SPRITE_PX = 48
# Cards stretch to fill the panel width — only the height is pinned. (A
# CARD_W constant used to live here but nothing applied it, which made it
# look like the width was fixed when it isn't.)
CARD_H = 72
# Action buttons sit in a 2×2 grid on the right of each card. They used to
# be a single column of four 18px-tall buttons: 4×18 + 3 gaps = 75px inside
# a 72px card, so they overflowed and read as one cramped strip. Two rows
# fit with room to spare AND leave each button big enough to hit.
ICON_BTN_W = 30
ICON_BTN_H = 27
ICON_BTN_GAP = 4


BALL_ICON_PX = 18


def _ball_icon_pixmap(ball_key: str) -> QPixmap:
    """Small icon showing which ball the buddy was caught with. Master ball
    uses its PokeAPI sprite; everything else falls back to the painted
    basic pokeball."""
    if ball_key == "special.master-ball":
        path = get_item_sprite("master-ball")
        if path is not None:
            pm = QPixmap(str(path))
            if not pm.isNull():
                return pm.scaled(BALL_ICON_PX, BALL_ICON_PX,
                                 Qt.KeepAspectRatio,
                                 Qt.SmoothTransformation)
    return make_pokeball_pixmap(BALL_ICON_PX)


def _icon_button(emoji: str, tip: str) -> QPushButton:
    btn = QPushButton(emoji)
    btn.setToolTip(tip)
    btn.setFixedSize(ICON_BTN_W, ICON_BTN_H)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(
        "QPushButton {"
        "  font-size: 11pt;"
        "  border: 1px solid #d5d5d5; border-radius: 5px;"
        "  background: #fbfbfb; padding: 0px;"
        "}"
        f"QPushButton:hover {{ background: {theme.tint_soft()};"
        f"  border-color: {theme.primary_light()}; }}"
        "QPushButton:pressed { background: #ececec; }"
        "QPushButton:disabled { color: #ccc; background: #f2f2f2;"
        "  border-color: #e6e6e6; }"
    )
    return btn


class _BagCard(QFrame):
    set_active = Signal(int)   # bag_id (= "make primary" / slot 0)
    party_toggle = Signal(int)  # bag_id — add to party / remove
    rename = Signal(int)
    release = Signal(int)
    show_detail = Signal(int)  # bag_id — opens PokemonDetailDialog

    def __init__(self, buddy: Buddy, sprite_style: str,
                 party_slot: Optional[int],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.bag_id = buddy.bag_id
        self.party_slot = party_slot   # 0/1/2 if in party, else None
        is_primary = party_slot == 0
        in_party = party_slot is not None
        self.setFixedHeight(CARD_H)
        self.setFrameShape(QFrame.StyledPanel)

        # Every card gets the same 1px frame — the party ones used to be
        # 2px, which shifted their content by a pixel and made the list
        # look ragged. Colour alone carries the distinction now.
        if is_primary:
            border = theme.primary()
            bg = theme.tint()
        elif in_party:
            border = theme.primary_light()
            bg = theme.tint_soft()
        elif buddy.is_rare:
            border = "#e6b14a"
            bg = "#fff8e8"
        else:
            border = "#bbb"
            bg = "#ffffff"
        self.setStyleSheet(
            f"_BagCard {{ background: {bg};"
            f"  border: 1px solid {border};"
            f"  border-radius: 6px; }}"
        )

        outer = QHBoxLayout(self)
        outer.setContentsMargins(4, 3, 4, 3)
        outer.setSpacing(6)

        path = get_buddy_sprite_with_fallback(sprite_style, buddy.dex_id,
                                              buddy.is_rare)
        self.sprite = AnimatedSprite(
            Path(path) if path else None,
            SPRITE_PX,
            parent=self,
        )
        outer.addWidget(self.sprite)

        middle = QVBoxLayout()
        middle.setSpacing(0)
        middle.setContentsMargins(0, 0, 0, 0)

        name_row = QHBoxLayout()
        name_row.setSpacing(4)
        name_row.setContentsMargins(0, 0, 0, 0)
        name_label = QLabel(buddy.display_name)
        name_font = QFont(); name_font.setBold(True); name_font.setPointSize(9)
        name_label.setFont(name_font)
        name_label.setStyleSheet("color: #222;")
        name_row.addWidget(name_label)
        if buddy.is_rare:
            badge = QLabel("✨")
            badge.setStyleSheet("font-size: 8pt;")
            name_row.addWidget(badge)
        # Party slot badge — only visible if this buddy is in the party.
        if in_party:
            slot_text = "대표" if is_primary else "파티"
            slot_badge = QLabel(slot_text)
            slot_color = (theme.primary() if is_primary
                          else theme.primary_light())
            slot_badge.setStyleSheet(
                f"color: {theme.on_primary()}; background: {slot_color};"
                "border-radius: 6px; padding: 0px 5px; font-size: 7pt;"
                "font-weight: bold;"
            )
            name_row.addWidget(slot_badge)
        name_row.addStretch(1)
        # Ball the buddy was caught with — master ball stands out visually.
        ball_label = QLabel()
        ball_label.setPixmap(_ball_icon_pixmap(buddy.caught_with))
        ball_label.setFixedSize(BALL_ICON_PX + 2, BALL_ICON_PX + 2)
        ball_label.setAlignment(Qt.AlignCenter)
        ball_label.setToolTip(
            "마스터볼로 잡음" if buddy.caught_with == "special.master-ball"
            else "몬스터볼로 잡음"
        )
        name_row.addWidget(ball_label)
        lvl = QLabel(f"Lv.{buddy.level}")
        lvl.setStyleSheet(
            f"color: {theme.on_primary()}; background: {theme.primary()};"
            "border-radius: 6px; padding: 0px 5px; font-size: 7pt;"
        )
        name_row.addWidget(lvl)
        middle.addLayout(name_row)

        hearts = buddy.hearts_bar
        # Card stays compact: hearts + EXP + friendship integer. The hidden
        # XP accumulator and the personality are reserved for the detail
        # dialog so the card list reads cleanly.
        stat = QLabel(
            f"{hearts}  EXP {buddy.exp}/{buddy.exp_to_next}  "
            f"친 {buddy.friendship}/100"
        )
        stat.setStyleSheet("color: #555; font-size: 7pt;")
        middle.addWidget(stat)
        middle.addStretch(1)

        outer.addLayout(middle, stretch=1)

        # 2×2 grid — reading order is  ⭐ 📋 / ✏️ 👑.
        btn_col = QGridLayout()
        btn_col.setSpacing(ICON_BTN_GAP)
        btn_col.setContentsMargins(0, 0, 0, 0)

        # Party toggle: ⭐ adds to party, ✓ marks already-in-party (click
        # to remove). Primary slot can't be removed directly — the user
        # promotes someone else first or releases.
        if in_party:
            party_btn = _icon_button("✓", "파티에서 제외")
        else:
            party_btn = _icon_button("⭐", "파티에 추가")
        party_btn.clicked.connect(
            lambda: self.party_toggle.emit(self.bag_id)
        )
        btn_col.addWidget(party_btn, 0, 0)

        detail_btn = _icon_button("📋", "상세보기")
        detail_btn.clicked.connect(lambda: self.show_detail.emit(self.bag_id))
        btn_col.addWidget(detail_btn, 0, 1)

        rename_btn = _icon_button("✏️", "이름 변경")
        rename_btn.clicked.connect(lambda: self.rename.emit(self.bag_id))
        btn_col.addWidget(rename_btn, 1, 0)

        # 4th slot is contextual: party members can be promoted to primary
        # (👑), non-party members can be released (🍃). Party members can't
        # be released directly — drop them from the party first.
        if in_party:
            promote_btn = _icon_button("👑", "대표로 설정")
            promote_btn.setEnabled(not is_primary)
            promote_btn.clicked.connect(
                lambda: self.set_active.emit(self.bag_id)
            )
            btn_col.addWidget(promote_btn, 1, 1)
        else:
            release_btn = _icon_button("📮", "박사에게 보내기")
            release_btn.clicked.connect(
                lambda: self.release.emit(self.bag_id)
            )
            btn_col.addWidget(release_btn, 1, 1)

        outer.addLayout(btn_col)


class BagPanel(QWidget):
    """One tab inside MainPanel — list of bag entries, active highlight,
    swap/rename/release controls. Emits `set_as_buddy(bag_id)` upward."""

    set_as_buddy = Signal(int)   # bag_id chosen
    bag_changed = Signal()        # rename / release
    show_detail = Signal(int)     # bag_id — open PokemonDetailDialog

    def __init__(self, store: Store, sprite_style: str, active_bag_id: int,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self.sprite_style = sprite_style
        self.active_bag_id = active_bag_id

        self._sprites: list[AnimatedSprite] = []

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(4, 2, 4, 2)
        self._root.setSpacing(4)

        bag = store.list_bag()
        rare_count = sum(1 for b in bag if b.is_rare)
        summary_text = f"{len(bag)}마리"
        if rare_count:
            summary_text += f"  ·  ✨ {rare_count}"
        self._summary = QLabel(summary_text)
        sf = QFont(); sf.setBold(True); sf.setPointSize(10)
        self._summary.setFont(sf)
        self._summary.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._root.addWidget(self._summary)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)

        self._inner = QWidget()
        self._inner_layout = QVBoxLayout(self._inner)
        self._inner_layout.setSpacing(3)
        self._inner_layout.setContentsMargins(2, 2, 2, 2)
        self._populate()

        scroll.setWidget(self._inner)
        self._root.addWidget(scroll, stretch=1)

    # ---- public ----
    def update_active(self, bag_id: int) -> None:
        """Called by MainPanel after the active buddy swaps elsewhere — keeps
        the highlighted card in sync without rebuilding the whole panel."""
        self.active_bag_id = bag_id
        self._populate()

    def refresh(self) -> None:
        self._populate()

    def cleanup(self) -> None:
        for s in self._sprites:
            s.stop()
        self._sprites.clear()

    # ---- internal ----
    def _populate(self) -> None:
        for s in self._sprites:
            s.stop()
        self._sprites.clear()
        while self._inner_layout.count():
            child = self._inner_layout.takeAt(0)
            w = child.widget()
            if w is not None:
                w.deleteLater()

        bag = self.store.list_bag()
        rare_count = sum(1 for b in bag if b.is_rare)
        summary_text = f"{len(bag)}마리"
        if rare_count:
            summary_text += f"  ·  ✨ {rare_count}"
        self._summary.setText(summary_text)

        # Partition into party (top, slot-ordered) and the rest (bottom).
        party_members: list = []
        non_party: list = []
        for buddy in bag:
            slot = self.store.party_slot(buddy.bag_id)
            if slot is not None:
                party_members.append((slot, buddy))
            else:
                non_party.append(buddy)
        party_members.sort(key=lambda x: x[0])

        def _add_card(buddy, slot):
            card = _BagCard(
                buddy, self.sprite_style,
                party_slot=slot,
                parent=self._inner,
            )
            card.party_toggle.connect(self._on_party_toggle)
            card.rename.connect(self._on_rename)
            card.release.connect(self._on_release)
            card.show_detail.connect(self.show_detail)
            card.set_active.connect(self.set_as_buddy)
            self._inner_layout.addWidget(card)
            self._sprites.append(card.sprite)

        # ---- party section ----
        party_header = QLabel(f"⭐ 파티  ({len(party_members)}/3)")
        party_header.setStyleSheet(
            f"color: {theme.on_primary()}; background: {theme.primary()};"
            "border-radius: 4px; padding: 3px 8px;"
            "font-weight: bold; font-size: 8pt;"
            "margin-top: 2px;"
        )
        self._inner_layout.addWidget(party_header)
        if party_members:
            for slot, buddy in party_members:
                _add_card(buddy, slot)
        else:
            empty = QLabel("파티가 비어있어. ⭐ 버튼으로 추가해줘.")
            empty.setStyleSheet(
                "color: #888; font-size: 8pt; padding: 6px 8px;"
            )
            self._inner_layout.addWidget(empty)

        # ---- storage section ----
        bag_header = QLabel(f"🎒 보관함  ({len(non_party)}마리)")
        bag_header.setStyleSheet(
            "color: white; background: #888;"
            "border-radius: 4px; padding: 3px 8px;"
            "font-weight: bold; font-size: 8pt;"
            "margin-top: 8px;"
        )
        self._inner_layout.addWidget(bag_header)
        for buddy in non_party:
            _add_card(buddy, None)
        self._inner_layout.addStretch(1)

    def _on_party_toggle(self, bag_id: int) -> None:
        """Add to party if not in, remove if in. Surfaces friendly messages
        when the user bumps the limits (party already full / can't remove
        the last buddy)."""
        slot = self.store.party_slot(bag_id)
        if slot is None:
            ok = self.store.add_to_party(bag_id)
            if not ok:
                # Party full — ask who steps out instead of sending the user
                # away to un-star someone first.
                if not self._swap_into_full_party(bag_id):
                    return
        else:
            ok = self.store.remove_from_party(bag_id)
            if not ok:
                QMessageBox.information(
                    self, "최소 1마리",
                    "파티에는 최소 한 마리는 있어야 합니다.",
                )
                return
        self.bag_changed.emit()
        self._populate()

    def _swap_into_full_party(self, incoming_bag_id: int) -> bool:
        """Let the user pick which party member the newcomer replaces.
        Returns True if a swap happened."""
        from PySide6.QtWidgets import QDialog
        from .buddy_picker import BuddyPickerDialog

        incoming = self.store.get_bag_entry(incoming_bag_id)
        if incoming is None:
            return False
        members = [b for b in (self.store.get_bag_entry(i)
                               for i in self.store.load_active_party())
                   if b is not None]
        if not members:
            return False

        dlg = BuddyPickerDialog(
            [(b, self.sprite_style) for b in members],
            f"파티가 가득 찼어. {incoming.display_name}와(과) 누구를 교체할까?",
            parent=self,
            title="파티 교체",
            action_label="교체",
        )
        if dlg.exec() != QDialog.Accepted or dlg.chosen_index is None:
            return False
        outgoing = members[dlg.chosen_index]
        # Swap in place so the 대표 slot doesn't silently shuffle.
        return self.store.swap_into_party(outgoing.bag_id, incoming_bag_id)

    def _on_rename(self, bag_id: int) -> None:
        entry = self.store.get_bag_entry(bag_id)
        if entry is None:
            return
        current = entry.nickname or ""
        name, ok = QInputDialog.getText(
            self, "이름 변경",
            f"{entry.species_label}의 새 이름:",
            text=current,
        )
        if not ok:
            return
        new_nick = name.strip() or None
        self.store.rename_bag_entry(bag_id, new_nick)
        self.bag_changed.emit()
        self._populate()

    def _on_release(self, bag_id: int) -> None:
        entry = self.store.get_bag_entry(bag_id)
        if entry is None:
            return
        if self.store.party_slot(bag_id) is not None:
            # Belt-and-suspenders: the 박사에게 보내기 button is hidden for party
            # members but block here too in case of a stale UI race.
            return
        display = entry.display_name
        # Wording is gentle ("박사에게 보내기") but the confirm has to stay
        # blunt — this removes the buddy for good, and the phrasing could
        # otherwise read as "parked somewhere I can fetch it back from".
        confirm = QMessageBox.question(
            self, "박사에게 보내기",
            f"{display}을(를) 박사에게 보낼까요?\n"
            f"내 가방에서 영구히 사라지고, 다시 데려올 수 없어요.",
        )
        if confirm != QMessageBox.Yes:
            return
        self.store.remove_from_bag(bag_id)
        self.bag_changed.emit()
        self._populate()
