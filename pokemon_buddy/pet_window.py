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
    QCursor,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QWidget

from .config import BUDDY_BOX_PX, SPEECH_BUBBLE_PX
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

    # ---- sprite source ----
    def set_sprite_path(self, path: Optional[Path]) -> None:
        if path is None or not Path(path).exists():
            self.sprite.set_static(_placeholder_pixmap(BUDDY_BOX_PX))
            return
        if str(path).lower().endswith(".gif"):
            self.sprite.set_gif(Path(path))
        else:
            self.sprite.set_static(QPixmap(str(path)))

    # ---- speech bubble ----
    def say(self, text: str, ms: int = 2500) -> None:
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
    def move_to_bottom_right(self, margin: int = 24) -> None:
        screen = self.screen() or QCursor.pos()
        if hasattr(screen, "availableGeometry"):
            geo = screen.availableGeometry()
        else:
            from PySide6.QtGui import QGuiApplication
            geo = QGuiApplication.primaryScreen().availableGeometry()
        x = geo.right() - self.width() - margin
        y = geo.bottom() - self.height() - margin
        self.move(x, y)
