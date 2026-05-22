"""Animated sprite widget used by the dex and bag card grids.

The key trick — borrowed from `SpriteWidget` — is to NEVER call
`QMovie.setScaledSize`. Some animated GIFs have per-frame size variance
(diff-encoded deltas, transparent padding, etc.); when setScaledSize is on,
each frame ends up rendered at a slightly different effective size, which
the user sees as 움찔움찔 (jittering) every frame.

Instead we keep each frame at its native pixel size and apply a single
fixed `base_scale` inside `paintEvent` via QTransform. Every frame thus
renders at exactly the same on-screen size, centered in the widget."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import (
    QColor,
    QImageReader,
    QMovie,
    QPainter,
    QPixmap,
    QTransform,
)
from PySide6.QtWidgets import QWidget


def _first_frame(path: Path) -> Optional[QPixmap]:
    if not path.exists():
        return None
    if path.suffix.lower() == ".gif":
        reader = QImageReader(str(path))
        if reader.canRead():
            img = reader.read()
            if not img.isNull():
                return QPixmap.fromImage(img)
        return None
    pm = QPixmap(str(path))
    return pm if not pm.isNull() else None


def _silhouette(pm: QPixmap,
                color: QColor = QColor(60, 60, 60)) -> QPixmap:
    out = QPixmap(pm.size())
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.drawPixmap(0, 0, pm)
    p.setCompositionMode(QPainter.CompositionMode_SourceIn)
    p.fillRect(out.rect(), color)
    p.end()
    return out


class AnimatedSprite(QWidget):
    """Fixed-size transparent widget that draws a QMovie frame (or a static
    pixmap) via paintEvent. The base scale is computed ONCE from the first
    frame's native size; every subsequent frame is drawn through the same
    QTransform so the displayed size never changes between frames."""

    def __init__(self, path: Optional[Path], target_size: int, *,
                 silhouette: bool = False,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(target_size, target_size)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self._target = target_size
        self._base_scale: float = 1.0
        self._frame: Optional[QPixmap] = None
        self._movie: Optional[QMovie] = None
        self._fallback_text: Optional[str] = None

        if path is None:
            self._fallback_text = "?"
            return

        p = Path(path)
        is_gif = p.suffix.lower() == ".gif"

        if silhouette or not is_gif:
            pm = _first_frame(p) if is_gif else QPixmap(str(p))
            if pm is None or pm.isNull():
                self._fallback_text = "?"
                return
            if silhouette:
                pm = _silhouette(pm)
            self._frame = pm
            self._compute_base_scale()
            return

        # GIF playback path — native frames + paintEvent transform.
        movie = QMovie(str(p))
        movie.setCacheMode(QMovie.CacheAll)
        movie.frameChanged.connect(self._on_frame_changed)
        movie.start()
        # Force the first frame so we have a pixmap + base_scale immediately.
        movie.jumpToFrame(0)
        self._frame = movie.currentPixmap()
        self._compute_base_scale()
        self._movie = movie

    # ---- internal ----
    def _compute_base_scale(self) -> None:
        if self._frame is None or self._frame.isNull():
            self._base_scale = 1.0
            return
        native_max = max(self._frame.width(), self._frame.height())
        if native_max <= 0:
            self._base_scale = 1.0
            return
        self._base_scale = self._target / native_max

    def _on_frame_changed(self, _frame_num: int) -> None:
        if self._movie is None:
            return
        self._frame = self._movie.currentPixmap()
        self.update()

    def stop(self) -> None:
        if self._movie is not None:
            try:
                self._movie.frameChanged.disconnect(self._on_frame_changed)
            except (RuntimeError, TypeError):
                pass
            self._movie.stop()
            self._movie.deleteLater()
            self._movie = None

    # ---- painting ----
    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        if self._frame is None or self._frame.isNull():
            if self._fallback_text:
                p.setPen(QColor("#aaa"))
                p.drawText(self.rect(), Qt.AlignCenter, self._fallback_text)
            p.end()
            return

        pm = self._frame
        # Pixel art (small natives) stays crisp without smoothing.
        if max(pm.width(), pm.height()) <= 96:
            p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        else:
            p.setRenderHint(QPainter.SmoothPixmapTransform, True)

        cx, cy = self.width() / 2.0, self.height() / 2.0
        t = QTransform()
        t.translate(cx, cy)
        t.scale(self._base_scale, self._base_scale)
        t.translate(-pm.width() / 2.0, -pm.height() / 2.0)
        p.setTransform(t)
        p.drawPixmap(QPointF(0.0, 0.0), pm)
        p.end()
