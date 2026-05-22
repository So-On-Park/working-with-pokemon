"""First-run onboarding — the user picks an adventurer name and reaches
into one of four pokéballs to receive a random starter.

Two pages in a QStackedWidget:
  1) Name input.
  2) Four pokéball buttons. Clicking one reveals a random pick from
     [이상해씨 #1, 파이리 #4, 꼬부기 #7, 피카츄 #25] with a small flourish,
     then enables the "시작!" button.

The dialog is intentionally unclosable mid-flow — it has no system close
button and ignores Escape, so a fresh launch always ends with a complete
seed. Cancelling on the very first step falls back to default values
(name="모험가", random starter) so the user never gets a half-initialized
state if Qt itself terminates the dialog.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeyEvent, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .pokeball import make_pokeball_pixmap


# The classic four — Bulbasaur / Charmander / Squirtle / Pikachu.
STARTER_CHOICES: list[tuple[int, str]] = [
    (1,  "이상해씨"),
    (4,  "파이리"),
    (7,  "꼬부기"),
    (25, "피카츄"),
]

BALL_SIZE = 84


class _PokeballButton(QPushButton):
    """A pokéball-styled button. Clicking it tells the dialog which slot
    the user picked; the actual reveal is done by the dialog."""

    def __init__(self, slot: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.slot = slot
        self.setFixedSize(BALL_SIZE + 12, BALL_SIZE + 12)
        self.setIcon(self._ball_icon())
        from PySide6.QtCore import QSize
        self.setIconSize(QSize(BALL_SIZE, BALL_SIZE))
        self.setStyleSheet(
            "QPushButton {"
            "  background: transparent; border: 2px solid transparent;"
            "  border-radius: 50px;"
            "}"
            "QPushButton:hover {"
            "  border-color: #4a7ddc; background: rgba(74,125,220,30);"
            "}"
            "QPushButton:pressed { background: rgba(74,125,220,80); }"
            "QPushButton:disabled { background: transparent; }"
        )

    @staticmethod
    def _ball_icon():
        from PySide6.QtGui import QIcon
        pm = make_pokeball_pixmap(BALL_SIZE)
        return QIcon(pm)


class OnboardingDialog(QDialog):
    """Returns `adventurer_name` and `chosen_dex_id` after exec(). Both
    are guaranteed to be set even if the user cancels — see fallbacks."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pokemon Buddy — 모험 시작")
        self.setMinimumSize(420, 360)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        # No window close button — the user must finish the flow.
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        self.adventurer_name: str = "모험가"
        self.chosen_dex_id: int = random.choice([d for d, _ in STARTER_CHOICES])
        self.chosen_name: str = next(
            n for d, n in STARTER_CHOICES if d == self.chosen_dex_id
        )

        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 16, 16, 16)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, stretch=1)

        self.stack.addWidget(self._build_name_page())
        self.stack.addWidget(self._build_pick_page())

    # ---- page 1: name ----
    def _build_name_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(8)

        title = QLabel("환영해, 모험가!")
        tf = QFont(); tf.setBold(True); tf.setPointSize(16)
        title.setFont(tf)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        sub = QLabel("처음 만나서 반가워.\n어떻게 불러주면 될까?")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("color: #555; font-size: 10pt;")
        layout.addWidget(sub)

        layout.addSpacing(8)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("이름을 입력해줘 (한글 OK)")
        self.name_input.setMaxLength(20)
        nf = QFont(); nf.setPointSize(12)
        self.name_input.setFont(nf)
        self.name_input.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.name_input)
        layout.addStretch(1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.next_btn = QPushButton("다음 →")
        self.next_btn.setFixedSize(120, 36)
        self.next_btn.clicked.connect(self._on_next_clicked)
        btn_row.addWidget(self.next_btn)
        layout.addLayout(btn_row)
        return page

    def _on_next_clicked(self) -> None:
        name = self.name_input.text().strip()
        if name:
            self.adventurer_name = name
        # else: stays as the default "모험가"
        self.stack.setCurrentIndex(1)

    # ---- page 2: pick a pokéball ----
    def _build_pick_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        title = QLabel("포켓볼 4개 중 하나를 골라봐!")
        tf = QFont(); tf.setBold(True); tf.setPointSize(13)
        title.setFont(tf)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        sub = QLabel("그 안에서 너와 함께할 친구가 나올 거야 ✨")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("color: #555; font-size: 9pt;")
        layout.addWidget(sub)

        ball_row = QHBoxLayout()
        ball_row.setSpacing(8)
        ball_row.addStretch(1)
        self._ball_buttons: list[_PokeballButton] = []
        for i in range(4):
            btn = _PokeballButton(slot=i)
            btn.clicked.connect(lambda _checked=False, s=i: self._on_ball_picked(s))
            ball_row.addWidget(btn)
            self._ball_buttons.append(btn)
        ball_row.addStretch(1)
        layout.addLayout(ball_row)

        # Reveal area: appears only AFTER a ball is picked.
        self.reveal_label = QLabel(
            "✨ 어떤 친구가 나올까? 하나를 골라봐!"
        )
        self.reveal_label.setAlignment(Qt.AlignCenter)
        self.reveal_label.setStyleSheet(
            "color: #4a7ddc; font-size: 11pt; padding: 12px;"
        )
        self.reveal_label.setMinimumHeight(60)
        layout.addWidget(self.reveal_label)

        layout.addStretch(1)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.start_btn = QPushButton("시작!")
        self.start_btn.setFixedSize(140, 40)
        sf = QFont(); sf.setBold(True); sf.setPointSize(11)
        self.start_btn.setFont(sf)
        self.start_btn.setEnabled(False)  # locked until a ball is picked
        self.start_btn.clicked.connect(self._finish)
        btn_row.addWidget(self.start_btn)
        layout.addLayout(btn_row)
        return page

    def _on_ball_picked(self, slot: int) -> None:
        # Disable every ball so the user can't reroll.
        for b in self._ball_buttons:
            b.setEnabled(False)
        # Random pick — the four balls are visually identical, but each
        # click reaches into the same lucky-dip pool.
        dex_id, name = random.choice(STARTER_CHOICES)
        self.chosen_dex_id = dex_id
        self.chosen_name = name
        self.reveal_label.setText(
            f"🎉 #{dex_id:04d} <b>{name}</b>(이)가 나왔어!\n"
            f"<span style='color:#888; font-size:9pt;'>"
            f"{self.adventurer_name}님과 함께 모험을 시작해보자.</span>"
        )
        self.start_btn.setEnabled(True)

    def _finish(self) -> None:
        self.done(QDialog.Accepted)

    # ---- block escape + close attempts ----
    def keyPressEvent(self, ev: QKeyEvent) -> None:  # noqa: N802
        if ev.key() == Qt.Key_Escape:
            ev.ignore()
            return
        super().keyPressEvent(ev)

    def closeEvent(self, ev) -> None:  # noqa: N802
        # If the user somehow closes mid-flow (e.g. Alt+F4), we still
        # commit whatever defaults we have so BuddyApp can boot cleanly.
        self.done(QDialog.Accepted)
        ev.accept()
