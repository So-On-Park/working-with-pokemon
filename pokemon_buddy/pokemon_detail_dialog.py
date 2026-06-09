"""Detail view for a single bag entry — opened from the 내 포켓몬 tab.

Modal dialog showing everything we know about this individual:
  - Animated sprite + display name + level
  - Species (with rare prefix), dex number, gender
  - Personality
  - Catch metadata (date/time, days since, which ball)
  - Stats (level / EXP / friendship — full XP detail here)
  - Weight + height from PokeAPI
  - Nickname change history

Read-only. Edits still go through the bag card's rename / release buttons."""

from __future__ import annotations

import datetime as _dt
import json as _json
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .animated_sprite import AnimatedSprite
from .config import FRIENDSHIP_XP_PER_POINT
from . import display_scale as _display_scale
from . import messages
from .pokeball import make_pokeball_pixmap
from . import pokemon_info
from .sprites import get_buddy_sprite_with_fallback, get_item_sprite
from .state import Buddy


SPRITE_PX = 96


def _fmt_datetime(ts: float) -> str:
    try:
        d = _dt.datetime.fromtimestamp(ts)
    except (OSError, ValueError, OverflowError):
        return "?"
    return d.strftime("%Y-%m-%d %H:%M")


def _fmt_age(caught_at: float) -> str:
    import time
    secs = max(0.0, time.time() - caught_at)
    days = int(secs // 86400)
    if days == 0:
        hours = int(secs // 3600)
        return "오늘 잡음" if hours < 1 else f"오늘 잡음 ({hours}시간 전)"
    if days < 30:
        return f"{days}일 전"
    months = days // 30
    rest = days % 30
    if rest == 0:
        return f"{months}개월 전"
    return f"{months}개월 {rest}일 전"


def _gender_label(code: str) -> str:
    return {"m": "♂ 수컷", "f": "♀ 암컷", "n": "— 무성"}.get(code, "—")


def _ball_label(ball_key: str) -> str:
    if ball_key == "special.master-ball":
        return "💎 마스터볼"
    return "🔴 몬스터볼"


def _ball_pixmap(ball_key: str, side: int = 22) -> QPixmap:
    if ball_key == "special.master-ball":
        p = get_item_sprite("master-ball")
        if p is not None:
            pm = QPixmap(str(p))
            if not pm.isNull():
                return pm.scaled(side, side, Qt.KeepAspectRatio,
                                 Qt.SmoothTransformation)
    return make_pokeball_pixmap(side)


def _row(label: str, value: str, *, value_color: str = "#222") -> QWidget:
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(8)
    k = QLabel(label)
    k.setStyleSheet("color: #888; font-size: 9pt;")
    k.setFixedWidth(90)
    h.addWidget(k)
    v = QLabel(value)
    v.setStyleSheet(f"color: {value_color}; font-size: 9pt;")
    v.setWordWrap(True)
    h.addWidget(v, stretch=1)
    return w


class PokemonDetailDialog(QDialog):
    """Modal info card. Constructed on demand from BuddyApp."""

    # Emitted when the user nudges the 표시 크기 spinbox. BuddyApp listens
    # and refreshes any agent currently rendering this dex_id.
    display_scale_changed = Signal(int, float)  # (dex_id, scale)

    def __init__(self, buddy: Buddy, sprite_style: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("포켓몬 상세")
        self.setMinimumSize(380, 540)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self._dex_id = buddy.dex_id
        self.bag_id = buddy.bag_id
        # Set True by the 보내기 button; BuddyApp acts on it after exec().
        self.send_requested = False

        self._sprites: List[AnimatedSprite] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 8)
        root.setSpacing(8)

        # ---- header: sprite + name block ----
        header = QHBoxLayout()
        header.setSpacing(12)

        sprite_path = get_buddy_sprite_with_fallback(
            sprite_style, buddy.dex_id, buddy.is_rare,
        )
        sprite = AnimatedSprite(
            Path(sprite_path) if sprite_path else None,
            SPRITE_PX,
        )
        self._sprites.append(sprite)
        header.addWidget(sprite)

        name_col = QVBoxLayout()
        name_col.setSpacing(2)
        name_lbl = QLabel(buddy.display_name)
        nf = QFont(); nf.setBold(True); nf.setPointSize(14)
        name_lbl.setFont(nf)
        name_lbl.setStyleSheet("color: #222;")
        name_col.addWidget(name_lbl)

        species_text = f"{buddy.species_label}  ·  #{buddy.dex_id:04d}"
        species_lbl = QLabel(species_text)
        species_color = "#c47b1c" if buddy.is_rare else "#666"
        species_lbl.setStyleSheet(f"color: {species_color}; font-size: 9pt;")
        name_col.addWidget(species_lbl)

        lvl_lbl = QLabel(f"Lv. {buddy.level}")
        lvl_lbl.setStyleSheet(
            "color: white; background: #4a7ddc;"
            "border-radius: 8px; padding: 1px 10px; font-size: 10pt;"
        )
        lvl_lbl.setMaximumWidth(70)
        name_col.addWidget(lvl_lbl)

        header.addLayout(name_col, stretch=1)
        root.addLayout(header)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("color: #ddd;")
        root.addWidget(divider)

        # ---- scrollable info section ----
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(6)
        inner_layout.setContentsMargins(0, 0, 0, 0)

        # Personality
        personality_label = messages.PERSONALITY_LABELS.get(
            messages.personality_for(buddy.personality), "?"
        )
        inner_layout.addWidget(_row("성격", personality_label,
                                     value_color="#6f4cd6"))

        # Gender (resolved deterministically from bag_id + species)
        gender_code = buddy.gender or pokemon_info.gender_for(
            buddy.dex_id, buddy.bag_id)
        inner_layout.addWidget(_row("성별", _gender_label(gender_code)))

        # Catch metadata
        inner_layout.addWidget(_row(
            "잡힌 날짜", f"{_fmt_datetime(buddy.caught_at)}  ({_fmt_age(buddy.caught_at)})",
        ))

        # Ball used to catch
        ball_row_w = QWidget()
        ball_h = QHBoxLayout(ball_row_w)
        ball_h.setContentsMargins(0, 0, 0, 0); ball_h.setSpacing(8)
        bk = QLabel("잡힌 볼")
        bk.setStyleSheet("color: #888; font-size: 9pt;")
        bk.setFixedWidth(90)
        ball_h.addWidget(bk)
        ball_icon = QLabel()
        ball_icon.setPixmap(_ball_pixmap(buddy.caught_with, 18))
        ball_icon.setFixedSize(20, 20)
        ball_h.addWidget(ball_icon)
        ball_text = QLabel(_ball_label(buddy.caught_with))
        ball_text.setStyleSheet("color: #222; font-size: 9pt;")
        ball_h.addWidget(ball_text, stretch=1)
        inner_layout.addWidget(ball_row_w)

        # Stats — EXP + friendship including the hidden XP detail.
        inner_layout.addWidget(_row(
            "경험치", f"{buddy.exp} / {buddy.exp_to_next}",
        ))
        hearts = "❤" * buddy.hearts + "♡" * (5 - buddy.hearts)
        if buddy.friendship >= 100:
            fr_text = f"{hearts}  {buddy.friendship}/100 (만렙 ✨)"
        else:
            fr_text = (f"{hearts}  {buddy.friendship}/100  "
                       f"(다음까지 {buddy.friendship_xp}/{FRIENDSHIP_XP_PER_POINT})")
        inner_layout.addWidget(_row("친밀도", fr_text, value_color="#a04060"))

        # Learned skills (기술) — compact value + ⓘ for the details, instead
        # of a long inline hint.
        from . import skills as _skills
        from .info_icon import InfoIcon
        learned = [s for s in (_skills.find(k) for k in buddy.learned_skills)
                   if s is not None]
        skill_w = QWidget()
        skill_h = QHBoxLayout(skill_w)
        skill_h.setContentsMargins(0, 0, 0, 0)
        skill_h.setSpacing(8)
        sk_key = QLabel("기술")
        sk_key.setStyleSheet("color: #888; font-size: 9pt;")
        sk_key.setFixedWidth(90)
        skill_h.addWidget(sk_key)
        if learned:
            sk_val = QLabel("  ·  ".join(f"📜 {s.name}" for s in learned))
            sk_val.setStyleSheet("color: #6f4cd6; font-size: 9pt;")
            skill_h.addWidget(sk_val)
            skill_h.addWidget(InfoIcon(
                "\n".join(f"{s.name} — {s.description}" for s in learned)
            ))
        else:
            sk_val = QLabel("아직 없음")
            sk_val.setStyleSheet("color: #999; font-size: 9pt;")
            skill_h.addWidget(sk_val)
            skill_h.addWidget(InfoIcon(
                "기술 교본(📜)을 전수하거나, 친밀도가 100인 친구가 "
                "레벨업하면 기술을 배워."
            ))
        skill_h.addStretch(1)
        inner_layout.addWidget(skill_w)

        # Weight + height from PokeAPI (cached). Offline → "확인 불가".
        info = pokemon_info.get_species_info(buddy.dex_id)
        if info is not None:
            inner_layout.addWidget(_row(
                "몸무게", f"{info['weight_kg']:.1f} kg",
            ))
            inner_layout.addWidget(_row(
                "키", f"{info['height_m']:.1f} m",
            ))
        else:
            inner_layout.addWidget(_row("몸무게", "확인 불가 (오프라인)"))
            inner_layout.addWidget(_row("키", "확인 불가 (오프라인)"))

        # Nickname history
        history_label = QLabel("이름 변경 기록")
        history_label.setStyleSheet("color: #888; font-size: 9pt;")
        history_label.setContentsMargins(0, 8, 0, 2)
        inner_layout.addWidget(history_label)

        try:
            history = _json.loads(buddy.nickname_history or "[]")
        except ValueError:
            history = []
        if not history:
            empty = QLabel("(없음 — 별명을 설정한 적 없음)")
            empty.setStyleSheet("color: #aaa; font-size: 8pt;")
            inner_layout.addWidget(empty)
        else:
            for i, entry in enumerate(reversed(history)):
                is_latest = (i == 0)
                nick = entry.get("nickname") or "(별명 해제)"
                set_at = entry.get("set_at", 0)
                line = f"• {nick}  —  {_fmt_datetime(set_at)}"
                if is_latest and buddy.nickname:
                    line += "   (현재)"
                hl = QLabel(line)
                hl.setStyleSheet(
                    f"color: {'#222' if is_latest else '#666'}; "
                    f"font-size: 8pt;"
                )
                inner_layout.addWidget(hl)

        inner_layout.addStretch(1)
        scroll.setWidget(inner)
        root.addWidget(scroll, stretch=1)

        # ---- display-scale control (applies live) ----
        scale_row = QHBoxLayout()
        scale_row.setSpacing(8)
        scale_label = QLabel("표시 크기 배율")
        scale_label.setStyleSheet("color: #888; font-size: 9pt;")
        scale_label.setFixedWidth(90)
        scale_row.addWidget(scale_label)
        self._scale_spin = QDoubleSpinBox()
        self._scale_spin.setRange(0.5, 3.0)
        self._scale_spin.setSingleStep(0.1)
        self._scale_spin.setDecimals(2)
        self._scale_spin.setValue(_display_scale.get(buddy.dex_id))
        self._scale_spin.setToolTip(
            "캐릭터가 작으면 1.3~1.8, 너무 크면 0.7~0.9. 기본 1.0, 최대 3.0. "
            "변경 즉시 데스크탑 펫에 반영돼 (창도 함께 커져서 잘리지 않아)."
        )
        self._scale_spin.valueChanged.connect(self._on_scale_changed)
        scale_row.addWidget(self._scale_spin)
        scale_row.addStretch(1)
        root.addLayout(scale_row)

        # Bottom buttons: 보내기(파일로 전송) + 닫기
        btn_row = QHBoxLayout()
        send_btn = QPushButton("📤 보내기")
        send_btn.setFixedHeight(26)
        send_btn.setToolTip("이 포켓몬을 파일로 내보내 다른 사람에게 보낼 수 있어 "
                            "(보내면 내 가방에서는 사라져).")
        send_btn.setStyleSheet(
            "QPushButton { background: #e8553e; color: white; border: none;"
            "  border-radius: 5px; padding: 0 12px; font-size: 9pt; }"
            "QPushButton:hover { background: #cf4631; }"
        )
        send_btn.clicked.connect(self._on_send_clicked)
        btn_row.addWidget(send_btn)
        btn_row.addStretch(1)
        close_btn = QPushButton("닫기")
        close_btn.setFixedSize(60, 26)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

    def _on_send_clicked(self) -> None:
        # Flag + close; BuddyApp handles the send after exec() returns so we
        # don't stack a confirm/animation dialog on top of this modal.
        self.send_requested = True
        self.accept()

    def _on_scale_changed(self, value: float) -> None:
        _display_scale.set_scale(self._dex_id, float(value))
        self.display_scale_changed.emit(self._dex_id, float(value))

    def closeEvent(self, ev) -> None:  # noqa: N802
        for s in self._sprites:
            s.stop()
        super().closeEvent(ev)
