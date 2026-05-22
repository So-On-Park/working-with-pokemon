"""Wild Pokemon window — just the floating sprite. No card, no buttons, no
text. Click on the sprite to trigger the catch sequence; otherwise the
Pokemon flees on its auto-flee timer."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtWidgets import QWidget

from .config import BUDDY_BOX_PX, ENCOUNTER_AUTO_FLEE_MS
from .pet_window import _placeholder_pixmap
from .sprite_widget import SpriteWidget


class WildPokemonWindow(QWidget):
    """A bare floating sprite. Emits `clicked` when the user taps the
    sprite. The encounter manager orchestrates everything after that."""

    clicked = Signal()
    flee_timeout = Signal()

    def __init__(self, dex_id: int, name: str,
                 sprite_path: Optional[Path], *,
                 is_rare: bool = False) -> None:
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self.dex_id = dex_id
        self.name = name
        self.is_rare = is_rare
        self._resolved = False

        self.setFixedSize(BUDDY_BOX_PX, BUDDY_BOX_PX)

        self.sprite = SpriteWidget(BUDDY_BOX_PX, self)
        self.sprite.move(0, 0)
        # SpriteWidget defaults to transparent-for-mouse-events; we want
        # the wild Pokemon to BE the click target, so re-enable input on it.
        self.sprite.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        self._load_sprite(sprite_path)

        self._auto_flee = QTimer(self)
        self._auto_flee.setSingleShot(True)
        self._auto_flee.timeout.connect(self._on_auto_flee)
        self._auto_flee.start(ENCOUNTER_AUTO_FLEE_MS)

    # ---- sprite ----
    def _load_sprite(self, path: Optional[Path]) -> None:
        if path is None or not Path(path).exists():
            from PySide6.QtGui import QPixmap
            self.sprite.set_static(_placeholder_pixmap(BUDDY_BOX_PX))
            return
        if str(path).lower().endswith(".gif"):
            self.sprite.set_gif(Path(path))
        else:
            from PySide6.QtGui import QPixmap
            self.sprite.set_static(QPixmap(str(path)))

    # ---- placement ----
    def place_random(self, screen_geo, avoid_rect) -> None:
        """Random spot on screen, avoiding overlap with `avoid_rect` (the
        buddy's geometry). Tries a handful of placements before giving up."""
        margin = 24
        min_x = screen_geo.left() + margin
        max_x = screen_geo.right() - self.width() - margin
        min_y = screen_geo.top() + margin
        max_y = screen_geo.bottom() - self.height() - margin

        for _ in range(20):
            x = random.randint(min_x, max(min_x, max_x))
            y = random.randint(min_y, max(min_y, max_y))
            r = self.geometry()
            r.moveTopLeft(QPoint(x, y))
            if not r.intersects(avoid_rect):
                self.move(x, y)
                return
        # Fallback — top-left
        self.move(min_x, min_y)

    # ---- mouse ----
    def mousePressEvent(self, ev) -> None:  # noqa: N802
        if self._resolved:
            return
        if ev.button() == Qt.LeftButton:
            self._resolved = True
            self._auto_flee.stop()
            self.clicked.emit()

    def allow_retry(self) -> None:
        """Re-arm the window for another click. Used when the catch attempt
        was rejected before the ball flew (e.g. empty Pokeball bag)."""
        self._resolved = False
        if not self._auto_flee.isActive():
            self._auto_flee.start(ENCOUNTER_AUTO_FLEE_MS)

    # ---- auto-flee ----
    def _on_auto_flee(self) -> None:
        if self._resolved:
            return
        self._resolved = True
        self.flee_timeout.emit()

    # ---- visual sequence helpers (driven by the manager) ----
    def absorb_into_ball(self, on_done: Callable[[], None]) -> None:
        """Shrink the sprite to zero — the Pokemon is being pulled into
        the ball at landing."""
        anim = QVariantAnimation(self)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setDuration(200)
        anim.setEasingCurve(QEasingCurve.InCubic)
        anim.valueChanged.connect(
            lambda v: self.sprite.set_transform(scale=float(v))
        )
        anim.finished.connect(on_done)
        anim.start()
        self._absorb_anim = anim
        self.hide()  # hide window during shake; we'll bring it back if it escapes

    def reappear(self, on_done: Callable[[], None]) -> None:
        """Burst back out of the ball on a failed catch."""
        self.show()
        self.raise_()
        anim = QVariantAnimation(self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(160)
        anim.setEasingCurve(QEasingCurve.OutBack)
        anim.valueChanged.connect(
            lambda v: self.sprite.set_transform(scale=float(v))
        )
        anim.finished.connect(on_done)
        anim.start()
        self._absorb_anim = anim

    def escape_off_screen(self, on_done: Callable[[], None]) -> None:
        """The Pokemon drifts upward and fades out — like a soul escaping
        skyward. 700ms, both fade and y-motion driven by the same
        QVariantAnimation so they stay in lockstep."""
        start_x = self.x()
        start_y = self.y()
        drift_px = 60

        anim = QVariantAnimation(self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(700)
        anim.setEasingCurve(QEasingCurve.InQuad)

        def on_value(v) -> None:
            t = float(v)
            self.move(start_x, int(start_y - drift_px * t))
            self.setWindowOpacity(1.0 - t)

        anim.valueChanged.connect(on_value)
        anim.finished.connect(on_done)
        anim.start()
        self._escape_anim = anim
