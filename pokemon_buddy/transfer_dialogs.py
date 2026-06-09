"""Reveal animations for sending / receiving a Pokemon.

ReceiveRevealDialog — plays when a `.pokeball` is imported:
    "두근두근… 새로운 포켓몬이다!" → pokéball wobbles → bursts open →
    "따단! ○○○이(가) 나의 동료가 되었어!" (+ dex-added note).

SendRevealDialog — plays after a confirmed 보내기:
    the buddy is drawn in, the ball closes with a sparkle →
    "○○○이 포켓볼에 잘 들어갔습니다" + the saved file path.
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
    QUrl,
)
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .animated_sprite import AnimatedSprite
from .pokeball import make_pokeball_pixmap
from .star_burst import StarBurst

STAGE_PX = 150
BALL_PX = 110
SPRITE_PX = 132


class _RevealBase(QDialog):
    """Shared scaffold: a centered 'stage' holding a pokéball label and a
    sprite, a headline label, a sub label, and a bottom button."""

    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setMinimumSize(360, 340)
        self._burst: Optional[StarBurst] = None
        self._anim: Optional[QPropertyAnimation] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 12)
        root.setSpacing(10)

        self.headline = QLabel("")
        hf = QFont(); hf.setBold(True); hf.setPointSize(13)
        self.headline.setFont(hf)
        self.headline.setAlignment(Qt.AlignCenter)
        self.headline.setWordWrap(True)
        self.headline.setStyleSheet("color: #4a7ddc;")
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

    def _wobble_ball(self, cycles: int = 8) -> None:
        base = self.ball.pos()
        anim = QPropertyAnimation(self.ball, b"pos", self)
        anim.setDuration(90)
        anim.setStartValue(QPoint(base.x() - 7, base.y()))
        anim.setEndValue(QPoint(base.x() + 7, base.y()))
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
        QTimer.singleShot(200, lambda: self._wobble_ball(8))
        QTimer.singleShot(1150, self._open_ball)

    def _open_ball(self) -> None:
        self._burst_at_ball()
        try:
            self.ball.setVisible(False)
        except RuntimeError:
            return
        sp = self._make_sprite(self._sprite_path)
        sp.show()
        rare = "✨ 레어 " if self._is_rare else ""
        self.headline.setText(f"따단! {rare}{self._display_name}이(가)\n나의 동료가 되었어!")
        note = "📖 도감에 새로 추가됐어!" if self._is_new_dex else f"({self._species_name})"
        self.sub.setText(note)
        self.action_btn.setText("반가워! ✨")
        self.action_btn.setVisible(True)
        self.action_btn.setDefault(True)


class SendRevealDialog(_RevealBase):
    """Send confirmation reveal — the buddy is drawn into the ball, which
    then shows where the file was saved."""

    def __init__(self, *, display_name: str, sprite_path: Optional[Path],
                 save_path: str, parent: Optional[QWidget] = None) -> None:
        super().__init__("포켓몬 보내기", parent)
        self._display_name = display_name
        self._save_path = save_path

        # Start with the buddy visible on top of the (hidden) ball.
        self.ball.setVisible(False)
        sp = self._make_sprite(sprite_path)
        sp.show()
        self.headline.setText(f"{display_name}을(를) 포켓볼에 넣는 중…")
        self.sub.setText("")
        QTimer.singleShot(900, self._draw_into_ball)

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
        self.sub.setText(f"저장 위치:\n{self._save_path}")
        self.action_btn.setText("확인")
        self.action_btn.setVisible(True)
        self.action_btn.setDefault(True)
        self.extra_btn.setText("폴더 열기")
        self.extra_btn.setVisible(True)
        self.extra_btn.clicked.connect(self._open_folder)

    def _open_folder(self) -> None:
        folder = str(Path(self._save_path).parent)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
