"""Star burst widget — the little confetti-of-stars that pops out of the
pokeball on a successful catch.

A short-lived frameless transparent window painted with 8 four-pointed
stars that radiate outward from the center as alpha fades 0→1→0. Lifetime
~600ms; the encounter manager destroys it via `on_done` once finished."""

from __future__ import annotations

import math
from typing import Callable

from PySide6.QtCore import QPoint, QPointF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget


BURST_SIZE = 96            # square widget side
STAR_COUNT = 8
MAX_RADIUS = 38            # peak distance from center
STAR_HALF = 5              # half-side of each 4-point star


class StarBurst(QWidget):
    """One-shot burst. Call `play_at(center_global, on_done)` and forget."""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
            | Qt.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedSize(BURST_SIZE, BURST_SIZE)

        self._t = 0.0   # 0 → 1 progress
        self._anim = None

    def play_at(self, center_global: QPoint,
                on_done: Callable[[], None],
                duration_ms: int = 600) -> None:
        # Center the widget on the requested global point.
        self.move(int(center_global.x() - BURST_SIZE / 2),
                  int(center_global.y() - BURST_SIZE / 2))
        self.show()
        self.raise_()

        anim = QVariantAnimation(self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(duration_ms)
        anim.valueChanged.connect(self._on_progress)
        anim.finished.connect(lambda: (self.hide(), on_done()))
        anim.start()
        self._anim = anim

    def _on_progress(self, v) -> None:
        self._t = float(v)
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802
        if self._t <= 0.0:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        cx = self.width() / 2.0
        cy = self.height() / 2.0

        # Alpha: smooth bell — fade in, peak around t=0.4, fade out.
        alpha = math.sin(self._t * math.pi)
        # Radius grows from 0 → MAX_RADIUS over the full duration.
        radius = MAX_RADIUS * self._t

        # Stars rotate a bit so the burst feels alive (one slow turn).
        base_angle = self._t * (math.pi / 4)

        color = QColor(255, 230, 110)
        color.setAlphaF(alpha)
        outline = QColor(255, 180, 40)
        outline.setAlphaF(alpha * 0.7)
        p.setBrush(color)
        p.setPen(QPen(outline, 0.8))

        for i in range(STAR_COUNT):
            angle = base_angle + i * (2 * math.pi / STAR_COUNT)
            sx = cx + math.cos(angle) * radius
            sy = cy + math.sin(angle) * radius
            self._draw_star(p, sx, sy, STAR_HALF)
        p.end()

    @staticmethod
    def _draw_star(p: QPainter, x: float, y: float, half: float) -> None:
        """4-pointed star (sparkle) centered at (x, y)."""
        thin = half * 0.32
        star = QPolygonF([
            QPointF(x,        y - half),
            QPointF(x + thin, y - thin),
            QPointF(x + half, y),
            QPointF(x + thin, y + thin),
            QPointF(x,        y + half),
            QPointF(x - thin, y + thin),
            QPointF(x - half, y),
            QPointF(x - thin, y - thin),
        ])
        p.drawPolygon(star)
