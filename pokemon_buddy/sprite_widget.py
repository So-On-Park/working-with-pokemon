"""Sprite widget that draws a QMovie (or static QPixmap) with a 2D transform
applied each frame. The transform — rotation, scale, dx, dy — is driven by the
animation engine and reset to identity for the IDLE state."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSize, Qt, QPointF
from PySide6.QtGui import (
    QColor,
    QMovie,
    QPainter,
    QPixmap,
    QRadialGradient,
    QTransform,
)
from PySide6.QtWidgets import QWidget

from .config import TARGET_DISPLAY_PX


class SpriteWidget(QWidget):
    """A square transparent widget that renders the active sprite (animated
    GIF or static PNG) with the current transform applied."""

    def __init__(self, box_px: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._box_px = box_px
        self.setFixedSize(box_px, box_px)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self._movie: Optional[QMovie] = None
        self._static_pixmap: Optional[QPixmap] = None
        self._frame_pixmap: Optional[QPixmap] = None

        # Base scale brings the native (often tiny) sprite up to a display-
        # friendly size — computed once per sprite source. Action animations
        # multiply onto this without modifying it.
        self._base_scale: float = 1.0
        # Per-sprite override applied AFTER the long-edge normalization.
        # Used for custom pokemon whose aspect ratio makes them look small
        # after the default fit (e.g. tall thin characters).
        self._scale_override: float = 1.0

        # Transform state — written by the animation engine
        self.rotation_deg: float = 0.0
        self.scale: float = 1.0
        self.dx: float = 0.0
        self.dy: float = 0.0

        # Halo state — written by AnimationEngine.play_halo. The halo is a
        # soft golden radial-gradient circle rendered BEHIND the sprite
        # for level-up moments. Stays at alpha=0 normally so it doesn't
        # add peripheral motion (motion-sensitive user).
        self.halo_alpha: float = 0.0
        self.halo_scale: float = 1.0

    # ---- sprite source ----
    def set_gif(self, path: Path) -> None:
        self._dispose_movie()
        self._static_pixmap = None
        mv = QMovie(str(path))
        mv.setCacheMode(QMovie.CacheAll)
        # NO setScaledSize — caused the per-frame flicker. Frames are kept at
        # native pixels and scaled later in paintEvent so the scale is stable.
        mv.frameChanged.connect(self._on_movie_frame_changed)
        self._movie = mv
        mv.start()
        # Force a first frame so the widget has something to paint immediately.
        mv.jumpToFrame(0)
        self._frame_pixmap = mv.currentPixmap()
        self._update_base_scale()
        self.update()

    def set_static(self, pixmap: QPixmap) -> None:
        self._dispose_movie()
        self._static_pixmap = pixmap
        self._frame_pixmap = pixmap
        self._update_base_scale()
        self.update()

    def _update_base_scale(self) -> None:
        if self._frame_pixmap is None or self._frame_pixmap.isNull():
            self._base_scale = 1.0
            return
        native_max = max(self._frame_pixmap.width(), self._frame_pixmap.height())
        if native_max <= 0:
            self._base_scale = 1.0
            return
        self._base_scale = (TARGET_DISPLAY_PX / native_max) * self._scale_override

    def set_scale_override(self, factor: float) -> None:
        """Multiplier applied after long-edge normalization. 1.0 = stock."""
        self._scale_override = max(0.1, float(factor))
        self._update_base_scale()
        self.update()

    def set_box(self, box_px: int) -> None:
        """Resize the drawing box. The sprite is drawn centered using the
        widget's current size, so growing the box gives a large scale the
        room it needs instead of clipping at the window edge."""
        self._box_px = int(box_px)
        self.setFixedSize(self._box_px, self._box_px)
        self.update()

    def _dispose_movie(self) -> None:
        if self._movie is not None:
            try:
                self._movie.frameChanged.disconnect(self._on_movie_frame_changed)
            except (RuntimeError, TypeError):
                pass
            self._movie.stop()
            self._movie.deleteLater()
            self._movie = None

    def _on_movie_frame_changed(self, _frame: int) -> None:
        if self._movie is None:
            return
        self._frame_pixmap = self._movie.currentPixmap()
        self.update()

    # ---- transform API ----
    def reset_transform(self) -> None:
        self.rotation_deg = 0.0
        self.scale = 1.0
        self.dx = 0.0
        self.dy = 0.0
        self.update()

    def set_transform(self, *, rotation_deg: float = 0.0, scale: float = 1.0,
                      dx: float = 0.0, dy: float = 0.0) -> None:
        self.rotation_deg = rotation_deg
        self.scale = scale
        self.dx = dx
        self.dy = dy
        self.update()

    # ---- painting ----
    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        cx, cy = self.width() / 2.0, self.height() / 2.0

        # Halo first so the sprite renders ON TOP of the glow. Drawn in
        # widget-local coords (not affected by the sprite transform) so
        # it stays anchored to the buddy's center even when the surprise
        # pop bounces the sprite.
        if self.halo_alpha > 0.01:
            base_radius = TARGET_DISPLAY_PX * 0.55
            radius = base_radius * self.halo_scale
            grad = QRadialGradient(QPointF(cx, cy), radius)
            center = QColor(255, 230, 120); center.setAlphaF(self.halo_alpha)
            mid = QColor(255, 200, 80);     mid.setAlphaF(self.halo_alpha * 0.45)
            edge = QColor(255, 180, 60);    edge.setAlphaF(0.0)
            grad.setColorAt(0.0, center)
            grad.setColorAt(0.6, mid)
            grad.setColorAt(1.0, edge)
            p.setBrush(grad)
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx, cy), radius, radius)

        if self._frame_pixmap is None or self._frame_pixmap.isNull():
            p.end()
            return

        pm = self._frame_pixmap
        # Pixel art (small sources) stays crisp without smoothing.
        if max(pm.width(), pm.height()) <= 96:
            p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        else:
            p.setRenderHint(QPainter.SmoothPixmapTransform, True)

        total_scale = self._base_scale * self.scale

        t = QTransform()
        t.translate(cx + self.dx, cy + self.dy)
        t.rotate(self.rotation_deg)
        t.scale(total_scale, total_scale)
        t.translate(-pm.width() / 2.0, -pm.height() / 2.0)
        p.setTransform(t)
        p.drawPixmap(QPointF(0.0, 0.0), pm)
        p.end()

    def native_size(self) -> QSize:
        if self._frame_pixmap is not None:
            return self._frame_pixmap.size()
        return QSize(0, 0)
