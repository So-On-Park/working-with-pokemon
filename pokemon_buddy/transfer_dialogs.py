"""Reveal animations for sending / receiving a Pokemon.

ReceiveRevealDialog — plays when a `.pokeball` is imported:
    "두근두근… 새로운 포켓몬이다!" → pokéball wobbles → bursts open →
    "따단! ○○○이(가) 나의 동료가 되었어!" (+ dex-added note).

SendRevealDialog — the 보내기 confirm + send-off in one window:
    the buddy says its goodbye → the user confirms ("보낼게요/아니요") →
    the buddy is drawn into the ball with a sparkle. (No file path shown.)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .animated_sprite import AnimatedSprite
from .pokeball import make_pokeball_pixmap
from .star_burst import StarBurst

STAGE_PX = 92
BALL_PX = 62
SPRITE_PX = 80   # ~base display size — imported buddy shouldn't look huge


class _RevealBase(QDialog):
    """Shared scaffold: a centered 'stage' holding a pokéball label and a
    sprite, a headline label, a sub label, and a bottom button."""

    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setMinimumSize(300, 250)
        self.resize(300, 250)
        self._burst: Optional[StarBurst] = None
        self._anim: Optional[QPropertyAnimation] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 12)
        root.setSpacing(10)

        self.headline = QLabel("")
        hf = QFont(); hf.setBold(True); hf.setPointSize(12)
        self.headline.setFont(hf)
        self.headline.setAlignment(Qt.AlignCenter)
        self.headline.setWordWrap(True)
        self.headline.setStyleSheet(f"color: {theme.primary()};")
        root.addWidget(self.headline)

        # Stage: ball + sprite overlaid, centered.
        stage_row = QHBoxLayout()
        stage_row.addStretch(1)
        self.stage = QWidget()
        self.stage.setFixedSize(STAGE_PX, STAGE_PX)
        self.ball = QLabel(self.stage)
        self.ball.setPixmap(make_pokeball_pixmap(BALL_PX))
        self.ball.setFixedSize(BALL_PX, BALL_PX)
        self.ball.move((STAGE_PX - BALL_PX) // 2, (STAGE_PX - BALL_PX) // 2)
        stage_row.addWidget(self.stage)
        stage_row.addStretch(1)
        root.addLayout(stage_row)

        self.sub = QLabel("")
        self.sub.setAlignment(Qt.AlignCenter)
        self.sub.setWordWrap(True)
        self.sub.setStyleSheet("color: #666; font-size: 9pt;")
        root.addWidget(self.sub)

        root.addStretch(1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.action_btn = QPushButton("")
        self.action_btn.setFixedHeight(34)
        self.action_btn.setVisible(False)
        self.action_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.action_btn)
        self.extra_btn = QPushButton("")
        self.extra_btn.setFixedHeight(34)
        self.extra_btn.setVisible(False)
        btn_row.addWidget(self.extra_btn)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

        self._sprite: Optional[AnimatedSprite] = None

    # ---- helpers ----
    def _make_sprite(self, sprite_path: Optional[Path]) -> AnimatedSprite:
        sp = AnimatedSprite(
            Path(sprite_path) if sprite_path else None, SPRITE_PX,
            parent=self.stage,
        )
        sp.move((STAGE_PX - SPRITE_PX) // 2, (STAGE_PX - SPRITE_PX) // 2)
        self._sprite = sp
        return sp

    def _wobble_ball(self, cycles: int = 3) -> None:
        """까딱… 까딱… 까딱 — `cycles` slow side nudges, each returning to
        center, so it reads as distinct wobbles rather than a fast jitter."""
        base = self.ball.pos()
        anim = QPropertyAnimation(self.ball, b"pos", self)
        anim.setDuration(340)  # per nudge — a touch slow on purpose
        anim.setKeyValueAt(0.0, base)
        anim.setKeyValueAt(0.30, QPoint(base.x() + 9, base.y()))
        anim.setKeyValueAt(0.60, QPoint(base.x() - 9, base.y()))
        anim.setKeyValueAt(1.0, base)
        anim.setEasingCurve(QEasingCurve.InOutSine)
        anim.setLoopCount(cycles)
        anim.finished.connect(lambda: self.ball.move(base))
        anim.start()
        self._anim = anim

    def _burst_at_ball(self) -> None:
        try:
            center = self.ball.mapToGlobal(
                QPoint(self.ball.width() // 2, self.ball.height() // 2))
            burst = StarBurst()
            burst.play_at(center, on_done=self._clear_burst)
            self._burst = burst
        except RuntimeError:
            pass

    def _clear_burst(self) -> None:
        b = self._burst
        self._burst = None
        if b is not None:
            try:
                b.hide(); b.deleteLater()
            except RuntimeError:
                pass

    def closeEvent(self, ev) -> None:  # noqa: N802
        if self._sprite is not None:
            try:
                self._sprite.stop()
            except RuntimeError:
                pass
        super().closeEvent(ev)


class ReceiveRevealDialog(_RevealBase):
    """Import reveal — ball wobbles, opens, the new buddy appears."""

    def __init__(self, *, display_name: str, species_name: str,
                 sprite_path: Optional[Path], is_new_dex: bool,
                 is_rare: bool = False, parent: Optional[QWidget] = None) -> None:
        super().__init__("새로운 포켓몬!", parent)
        self._display_name = display_name
        self._species_name = species_name
        self._sprite_path = sprite_path
        self._is_new_dex = is_new_dex
        self._is_rare = is_rare

        self.headline.setText("두근두근… 새로운 포켓몬이다!")
        self.sub.setText("몬스터볼이 들썩이고 있어…")
        QTimer.singleShot(300, lambda: self._wobble_ball(3))
        QTimer.singleShot(1400, self._open_ball)

    def _open_ball(self) -> None:
        try:
            self.ball.setVisible(False)
        except RuntimeError:
            return
        sp = self._make_sprite(self._sprite_path)
        sp.show()
        # 빵빠레 — fanfare burst as the buddy pops out.
        self._burst_at_ball()
        rare = "✨ " if self._is_rare else ""
        self.headline.setText(f"따단! {rare}{self._display_name}이(가)\n나의 동료가 되었어!")
        note = "📖 도감에 새로 추가됐어!" if self._is_new_dex else f"({self._species_name})"
        self.sub.setText(note)
        self.action_btn.setText("반가워! ✨")
        self.action_btn.setVisible(True)
        self.action_btn.setDefault(True)


class SendRevealDialog(_RevealBase):
    """Send flow: the buddy says its goodbye, the user confirms ONE more time,
    then the buddy is drawn into the ball. exec() returns Accepted only if the
    user goes through with it — the caller writes the file + removes the buddy
    after that."""

    def __init__(self, *, display_name: str, sprite_path: Optional[Path],
                 farewell: str = "",
                 parent: Optional[QWidget] = None) -> None:
        super().__init__("포켓몬 보내기", parent)
        self._display_name = display_name
        self._suck_anim: Optional[QPropertyAnimation] = None

        # Buddy visible on top of the (hidden) ball; it speaks its goodbye —
        # just the line itself (no "이름: ..." prefix).
        self.ball.setVisible(False)
        sp = self._make_sprite(sprite_path)
        sp.show()
        self.headline.setText(farewell or f"{display_name}을(를) 보냅니다")
        self.sub.setText("정말 보낼까요?")

        # One more yes/no before the ball closes. action_btn's default accept
        # wiring is repurposed to "confirm send" first.
        try:
            self.action_btn.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        self.action_btn.setText("보낼게요")
        self.action_btn.setVisible(True)
        self.action_btn.setDefault(True)
        self.action_btn.clicked.connect(self._confirm_send)
        self.extra_btn.setText("아니요")
        self.extra_btn.setVisible(True)
        self.extra_btn.clicked.connect(self.reject)

    def _confirm_send(self) -> None:
        # User said yes → hide buttons, run the 슈슉 animation.
        self.action_btn.setVisible(False)
        self.extra_btn.setVisible(False)
        self.sub.setText("포켓볼에 넣는 중…")
        self._suck_in()

    def _suck_in(self) -> None:
        """슈슉 — fade the buddy into the ball, then close the ball."""
        sp = self._sprite
        if sp is None:
            self._draw_into_ball()
            return
        try:
            eff = QGraphicsOpacityEffect(sp)
            sp.setGraphicsEffect(eff)
            anim = QPropertyAnimation(eff, b"opacity", self)
            anim.setDuration(420)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.setEasingCurve(QEasingCurve.InCubic)
            anim.finished.connect(self._draw_into_ball)
            anim.start()
            self._suck_anim = anim
        except RuntimeError:
            self._draw_into_ball()

    def _draw_into_ball(self) -> None:
        try:
            if self._sprite is not None:
                self._sprite.stop()
                self._sprite.setVisible(False)
            self.ball.setVisible(True)
        except RuntimeError:
            return
        self._burst_at_ball()
        self.headline.setText(f"{self._display_name}이(가)\n포켓볼에 잘 들어갔습니다!")
        self.sub.setText("")
        try:
            self.action_btn.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        self.action_btn.setText("확인")
        self.action_btn.setVisible(True)
        self.action_btn.setDefault(True)
        self.action_btn.clicked.connect(self.accept)
