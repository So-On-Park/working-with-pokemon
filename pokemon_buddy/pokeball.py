"""Pokeball widget — a tiny painted Pokeball that flies along a parabolic
arc, shakes a few times, then resolves into a success or failure visual.

It's a top-level transparent always-on-top window with input transparency,
so it never steals clicks while the user is mid-throw."""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPointF,
    QRectF,
    QSequentialAnimationGroup,
    Qt,
    QVariantAnimation,
)
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget


BALL_SIZE = 28


# ---- shared painting ----
def paint_pokeball(painter: QPainter, cx: float, cy: float, radius: float,
                   opacity: float = 1.0, *, dim: bool = False) -> None:
    """Draw a classic pokeball into `painter` centered at (cx, cy).

    Used both by the live flying Pokeball widget and by the static icon
    pixmaps shown in the inventory / item-drop UI. `dim=True` uses muted
    grays — for 'I don't own any of this' tiles."""
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)

    rect = QRectF(cx - radius, cy - radius, 2 * radius, 2 * radius)

    outline_color = QColor(160, 160, 160) if dim else QColor(20, 20, 20)
    outline = QColor(outline_color); outline.setAlphaF(opacity)
    painter.setPen(QPen(outline, max(1.0, radius * 0.08)))

    if dim:
        red_c = QColor(210, 175, 180)
        white_c = QColor(240, 240, 240)
    else:
        red_c = QColor(232, 52, 76)
        white_c = QColor(244, 244, 244)

    red = QColor(red_c); red.setAlphaF(opacity)
    painter.setBrush(red)
    painter.drawChord(rect, 0, 180 * 16)

    white = QColor(white_c); white.setAlphaF(opacity)
    painter.setBrush(white)
    painter.drawChord(rect, 180 * 16, 180 * 16)

    # Middle band
    band = QColor(outline_color); band.setAlphaF(opacity)
    painter.setBrush(band)
    painter.setPen(Qt.NoPen)
    band_h = max(2.0, radius * 0.18)
    painter.drawRect(QRectF(cx - radius, cy - band_h / 2,
                            2 * radius, band_h))

    # Center button
    btn_face = QColor(white_c); btn_face.setAlphaF(opacity)
    painter.setBrush(btn_face)
    painter.setPen(QPen(outline, max(0.8, radius * 0.06)))
    b = radius * 0.28
    painter.drawEllipse(QRectF(cx - b, cy - b, 2 * b, 2 * b))

    painter.restore()


def make_pokeball_pixmap(size: int, *, dim: bool = False) -> QPixmap:
    """Stand-alone pokeball as a QPixmap, ready to drop into a QLabel."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    r = size / 2.0 - max(1.0, size * 0.05)
    paint_pokeball(p, size / 2.0, size / 2.0, r, dim=dim)
    p.end()
    return pm


class Pokeball(QWidget):
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
        self.setFixedSize(BALL_SIZE, BALL_SIZE)

        self._rotation = 0.0
        self._scale = 1.0
        self._opacity_internal = 1.0   # painted into the pixmap (so alpha is independent of windowOpacity)
        self._anim: Optional[object] = None  # keep refs alive

    # ---- paint ----
    def paintEvent(self, _e) -> None:  # noqa: N802
        if self._scale <= 0.01:
            return
        p = QPainter(self)
        cx, cy = self.width() / 2.0, self.height() / 2.0
        p.translate(cx, cy)
        p.rotate(self._rotation)
        p.scale(self._scale, self._scale)
        r = self.width() / 2.0 - 2.0
        paint_pokeball(p, 0.0, 0.0, r, opacity=self._opacity_internal)
        p.end()

    # ---- helpers ----
    def _set_pos_centered(self, x: float, y: float) -> None:
        self.move(int(x - self.width() / 2), int(y - self.height() / 2))

    # ---- animations ----
    def fly_to(self, start_global: QPoint, end_global: QPoint,
               on_arrived: Callable[[], None],
               duration_ms: int = 520,
               arc_peak: float = 70.0) -> None:
        """Parabolic flight from start to end. Calls `on_arrived` at landing."""
        self._set_pos_centered(start_global.x(), start_global.y())
        self.show()
        self.raise_()

        anim = QVariantAnimation(self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(duration_ms)
        anim.setEasingCurve(QEasingCurve.OutQuad)

        sx, sy = float(start_global.x()), float(start_global.y())
        ex, ey = float(end_global.x()),  float(end_global.y())

        def on_value(v) -> None:
            t = float(v)
            x = sx + (ex - sx) * t
            y = sy + (ey - sy) * t - arc_peak * 4.0 * t * (1.0 - t)
            self._rotation = 540.0 * t  # spin during flight (1.5 turns)
            self._set_pos_centered(x, y)
            self.update()

        anim.valueChanged.connect(on_value)
        anim.finished.connect(lambda: (self._settle_rotation(), on_arrived()))
        anim.start()
        self._anim = anim

    def _settle_rotation(self) -> None:
        self._rotation = 0.0
        self.update()

    def shake(self, on_done: Callable[[], None],
              cycles: int = 4, cycle_ms: int = 500,
              amplitude_deg: float = 16.0) -> None:
        """Shake left-right `cycles` times, then call `on_done`. Defaults
        give a ~2 second tense pause (4 × 500ms) — long enough for the
        user to wonder whether the catch succeeded."""
        group = QSequentialAnimationGroup(self)
        for i in range(cycles):
            # right
            a = QVariantAnimation(self)
            a.setStartValue(0.0); a.setEndValue(amplitude_deg)
            a.setDuration(cycle_ms // 4)
            a.setEasingCurve(QEasingCurve.OutSine)
            a.valueChanged.connect(self._apply_rotation)
            group.addAnimation(a)
            # back
            b = QVariantAnimation(self)
            b.setStartValue(amplitude_deg); b.setEndValue(-amplitude_deg)
            b.setDuration(cycle_ms // 2)
            b.setEasingCurve(QEasingCurve.InOutSine)
            b.valueChanged.connect(self._apply_rotation)
            group.addAnimation(b)
            # back to zero
            c = QVariantAnimation(self)
            c.setStartValue(-amplitude_deg); c.setEndValue(0.0)
            c.setDuration(cycle_ms // 4)
            c.setEasingCurve(QEasingCurve.InSine)
            c.valueChanged.connect(self._apply_rotation)
            group.addAnimation(c)
        group.finished.connect(on_done)
        group.start()
        self._anim = group

    def _apply_rotation(self, v) -> None:
        self._rotation = float(v)
        self.update()

    def finish_success(self, on_done: Callable[[], None]) -> None:
        """Settle then fade out."""
        anim = QVariantAnimation(self)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setDuration(380)
        anim.setEasingCurve(QEasingCurve.InCubic)
        anim.valueChanged.connect(self._apply_internal_opacity)
        anim.finished.connect(lambda: (self.hide(), on_done()))
        anim.start()
        self._anim = anim

    def return_to(self, dest_global: QPoint,
                  on_done: Callable[[], None],
                  duration_ms: int = 480) -> None:
        """Fly the ball from its current location back to a target point
        (typically the buddy's center) on a gentle arc, fading out toward
        the end. Used on successful catches — the ball 'goes home' to the
        trainer instead of just disappearing in place."""
        start = self.frameGeometry().center()
        sx, sy = float(start.x()), float(start.y())
        ex, ey = float(dest_global.x()), float(dest_global.y())
        # Small inverse arc so the ball lifts before settling down to the
        # buddy — feels more 'reeled in' than a straight line.
        arc_peak = 40.0

        anim = QVariantAnimation(self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(duration_ms)
        anim.setEasingCurve(QEasingCurve.OutQuad)

        def on_value(v) -> None:
            t = float(v)
            x = sx + (ex - sx) * t
            y = sy + (ey - sy) * t - arc_peak * 4.0 * t * (1.0 - t)
            self._rotation = 360.0 * t  # one full spin on the way home
            self._set_pos_centered(x, y)
            # Soft fade-out across the final ~40% of the flight.
            if t > 0.6:
                self._opacity_internal = max(0.0, 1.0 - (t - 0.6) / 0.4)
            self.update()

        anim.valueChanged.connect(on_value)
        anim.finished.connect(lambda: (self.hide(), on_done()))
        anim.start()
        self._anim = anim

    def finish_fail(self, on_done: Callable[[], None]) -> None:
        """Pop open: scale up briefly, then disappear."""
        scale_up = QVariantAnimation(self)
        scale_up.setStartValue(1.0); scale_up.setEndValue(1.35)
        scale_up.setDuration(140)
        scale_up.setEasingCurve(QEasingCurve.OutQuad)
        scale_up.valueChanged.connect(self._apply_scale)

        fade = QVariantAnimation(self)
        fade.setStartValue(1.0); fade.setEndValue(0.0)
        fade.setDuration(200)
        fade.valueChanged.connect(self._apply_internal_opacity)

        group = QSequentialAnimationGroup(self)
        group.addAnimation(scale_up)
        group.addAnimation(fade)
        group.finished.connect(lambda: (self.hide(), on_done()))
        group.start()
        self._anim = group

    def _apply_internal_opacity(self, v) -> None:
        self._opacity_internal = float(v)
        self.update()

    def _apply_scale(self, v) -> None:
        self._scale = float(v)
        self.update()
