"""Small modal that asks the user which party member should receive a
per-buddy action (special items, mainly). Bypassed when there's only one
party member — caller falls back to the single agent directly."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


log = logging.getLogger(__name__)


PREVIEW_PX = 56


class BuddyPickerDialog(QDialog):
    """Returns the chosen index via `chosen_index` after exec().
    None means the user cancelled."""

    def __init__(self, agents, item_label: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("적용 대상")
        self.setMinimumWidth(320)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.chosen_index: Optional[int] = None

        # Lazy import — avoid pulling sprites at module import time.
        from .sprites import get_buddy_sprite_with_fallback

        root = QVBoxLayout(self)
        root.setSpacing(8)

        intro = QLabel(f"{item_label} — 어느 포켓몬에게 쓸까?")
        intro_font = QFont(); intro_font.setBold(True); intro_font.setPointSize(10)
        intro.setFont(intro_font)
        root.addWidget(intro)

        # One row per party member: sprite preview + name + use button.
        for idx, agent in enumerate(agents):
            row = QHBoxLayout()
            row.setSpacing(8)

            preview = QLabel()
            preview.setFixedSize(PREVIEW_PX, PREVIEW_PX)
            preview.setAlignment(Qt.AlignCenter)
            sprite_path = get_buddy_sprite_with_fallback(
                agent.sprite_style, agent.buddy.dex_id, agent.buddy.is_rare,
            )
            if sprite_path is not None:
                pm = QPixmap(str(Path(sprite_path)))
                if not pm.isNull():
                    preview.setPixmap(
                        pm.scaled(PREVIEW_PX, PREVIEW_PX,
                                  Qt.KeepAspectRatio,
                                  Qt.SmoothTransformation)
                    )
            row.addWidget(preview)

            name_col = QVBoxLayout()
            name_lbl = QLabel(agent.buddy.display_name)
            nf = QFont(); nf.setBold(True); nf.setPointSize(10)
            name_lbl.setFont(nf)
            name_col.addWidget(name_lbl)
            sub = QLabel(
                f"Lv. {agent.buddy.level}  ·  친 {agent.buddy.friendship}/100"
            )
            sub.setStyleSheet("color: #666; font-size: 8pt;")
            name_col.addWidget(sub)
            row.addLayout(name_col, stretch=1)

            pick_btn = QPushButton("선택")
            pick_btn.setFixedSize(60, 28)
            pick_btn.clicked.connect(lambda _checked=False, i=idx: self._pick(i))
            row.addWidget(pick_btn)

            root.addLayout(row)

        # Cancel
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel = QPushButton("취소")
        cancel.setFixedSize(60, 26)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        root.addLayout(btn_row)

    def _pick(self, idx: int) -> None:
        log.debug("BuddyPickerDialog._pick idx=%d", idx)
        self.chosen_index = idx
        # done(Accepted) ends exec() more deterministically than accept()
        # on this stack — same workaround as CustomPokemonDialog.
        self.done(QDialog.Accepted)
        log.debug("  done() returned")


def pick_buddy(agents: List, item_label: str,
               parent: QWidget | None = None):
    """Convenience: if there's exactly one party member, return it without
    prompting. Otherwise show the dialog and return the chosen agent or
    None on cancel."""
    log.debug("pick_buddy: %d agents, label=%s", len(agents), item_label)
    if not agents:
        return None
    if len(agents) == 1:
        return agents[0]
    dlg = BuddyPickerDialog(agents, item_label, parent=parent)
    log.debug("  dialog built, calling exec()")
    result = dlg.exec()
    log.debug("  exec() returned %r (Accepted=%r), chosen_index=%r",
             int(result), int(QDialog.Accepted), dlg.chosen_index)
    if result != QDialog.Accepted:
        return None
    if dlg.chosen_index is None:
        return None
    return agents[dlg.chosen_index]
