"""Floating desktop pet window.

The visible pet is a SpriteWidget — a custom transparent widget that renders
the current sprite frame with a 2D transform applied each repaint. Action
animations (feed, click, level up, typing-dance, …) are driven by an
AnimationEngine that lives outside this window and writes the transform."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QWidget

import math

from .config import BUDDY_BOX_PX, SPEECH_BUBBLE_PX, TARGET_DISPLAY_PX
from .speech_bubble import SpeechBubble
from .sprite_widget import SpriteWidget


def _placeholder_pixmap(size: int) -> QPixmap:
    """Friendly blob — shown when downloads fail and nothing is cached."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#f6c453"))
    p.setPen(QPen(QColor("#7a5a16"), 3))
    p.drawEllipse(size // 6, size // 4, size * 2 // 3, size * 2 // 3)
    p.setBrush(QColor("#222"))
    p.setPen(Qt.NoPen)
    eye_y = size // 2
    p.drawEllipse(size * 2 // 5, eye_y, 8, 8)
    p.drawEllipse(size * 3 // 5, eye_y, 8, 8)
    p.end()
    return pm


def _scaled_pixmap(path: Path, side: int) -> QPixmap:
    """Used by the encounter window where a larger render is needed."""
    pm = QPixmap(str(path))
    if pm.isNull():
        return _placeholder_pixmap(side)
    mode = (Qt.FastTransformation
            if max(pm.width(), pm.height()) <= 96
            else Qt.SmoothTransformation)
    return pm.scaled(side, side, Qt.KeepAspectRatio, mode)


class PetWindow(QWidget):
    """Frameless always-on-top floating pet."""

    play_requested = Signal()       # left-click on the buddy
    popup_requested = Signal(QRect) # right-click — sends buddy global rect

    DRAG_THRESHOLD = 6

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_AlwaysShowToolTips, True)

        box = BUDDY_BOX_PX
        self._box = box
        self.resize(box, box)

        # Sprite widget fills the window
        self.sprite = SpriteWidget(box, self)
        self.sprite.move(0, 0)

        # Speech bubble — its own top-level window, anchored to this one.
        self._bubble = SpeechBubble()

        # Drag state
        self._press_global: Optional[QPoint] = None
        self._is_dragging = False

        # Tooltip text
        self._status_text = ""

        # 조용히 시키기 — see set_muted().
        self._muted = False

    # ---- sprite source ----
    def set_sprite_path(self, path: Optional[Path]) -> None:
        if path is None or not Path(path).exists():
            self.sprite.set_static(_placeholder_pixmap(BUDDY_BOX_PX))
            return
        if str(path).lower().endswith(".gif"):
            self.sprite.set_gif(Path(path))
        else:
            self.sprite.set_static(QPixmap(str(path)))

    # ---- display scale ----
    @staticmethod
    def _box_for_scale(scale: float) -> int:
        """Window side needed so a sprite at the given display scale isn't
        clipped. The sprite's long edge renders at TARGET_DISPLAY_PX * scale;
        the 1.45 headroom leaves room for the action animations (surprise pop
        ≈ 1.25×, happy bob, dx/dy nudges). Never shrinks below the default."""
        needed = int(math.ceil(TARGET_DISPLAY_PX * max(0.1, scale) * 1.45))
        return max(BUDDY_BOX_PX, needed)

    def set_display_scale(self, scale: float) -> None:
        """Apply a per-dex display scale: push it into the sprite AND resize
        the window so larger scales get the room they need. The window grows
        about its own center so the buddy stays put on screen."""
        self.sprite.set_scale_override(scale)
        box = self._box_for_scale(scale)
        if box == self._box:
            return
        center = self.frameGeometry().center()
        self._box = box
        self.sprite.set_box(box)
        self.sprite.move(0, 0)
        self.resize(box, box)
        self.move(center.x() - box // 2, center.y() - box // 2)
        self._bubble.update_anchor(self.frameGeometry())

    # ---- speech bubble ----
    def set_muted(self, muted: bool) -> None:
        """조용히 시키기 — suppress every bubble from this buddy.

        Enforced here rather than at each call site because `say()` is the
        single door every line goes through (chatter, level-up, items,
        evolution, reminders). The status tooltip keeps updating, so the
        buddy is quiet, not blind."""
        self._muted = muted
        if muted:
            self._bubble.hide()

    def say(self, text: str, ms: int = 2500) -> None:
        if self._muted:
            return
        self._bubble.show_text(text, ms, self.frameGeometry())

    def set_status_text(self, text: str) -> None:
        self._status_text = text
        self.setToolTip(text)

    def moveEvent(self, ev) -> None:  # noqa: N802
        # Keep the speech bubble glued to the buddy when dragged.
        self._bubble.update_anchor(self.frameGeometry())
        super().moveEvent(ev)

    # ---- mouse: drag + click + context menu ----
    def mousePressEvent(self, ev) -> None:  # noqa: N802
        if ev.button() == Qt.LeftButton:
            self._press_global = ev.globalPosition().toPoint()
            self._is_dragging = False
        elif ev.button() == Qt.RightButton:
            # Hand off to BuddyApp which builds the animated popup.
            self.popup_requested.emit(self.frameGeometry())

    def mouseMoveEvent(self, ev) -> None:  # noqa: N802
        if self._press_global is None:
            return
        delta = ev.globalPosition().toPoint() - self._press_global
        if (not self._is_dragging
                and (abs(delta.x()) + abs(delta.y())) > self.DRAG_THRESHOLD):
            self._is_dragging = True
        if self._is_dragging:
            self.move(self.pos() + delta)
            self._press_global = ev.globalPosition().toPoint()

    def mouseReleaseEvent(self, ev) -> None:  # noqa: N802
        if ev.button() == Qt.LeftButton and not self._is_dragging:
            self.play_requested.emit()
        self._press_global = None
        self._is_dragging = False

    # ---- placement ----
    def move_to_bottom_right(self, margin: int = 24, *, x_offset: int = 0,
                             primary_screen: bool = False) -> None:
        """Park the window at the bottom-right of a screen.

        `margin` insets from both edges. `x_offset` shifts further LEFT
        only — a party lined up via `margin` alone drifted diagonally
        up-left, one step per slot, instead of standing in a row.

        `primary_screen` pins the placement to the main monitor rather than
        whichever screen Qt happens to associate with a not-yet-shown
        window."""
        from PySide6.QtGui import QGuiApplication
        screen = None if primary_screen else self.screen()
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        x = geo.right() - self.width() - margin - x_offset
        y = geo.bottom() - self.height() - margin
        self.move(x, y)
