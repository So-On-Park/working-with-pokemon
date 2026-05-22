"""Floating speech bubble — its own frameless top-level window so it can
extend beyond the buddy's tiny footprint and wrap long lines."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QPointF, QRect, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QPainter,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import QWidget


class SpeechBubble(QWidget):
    """API: `show_text(text, ms, anchor_rect)`. Auto-sizes to fit, wraps at
    `MAX_TEXT_WIDTH`. Position follows the anchor when `update_anchor` is
    called by the buddy on move."""

    MAX_TEXT_WIDTH = 300
    PAD_X = 12
    PAD_Y = 8
    TAIL_H = 8
    GAP = 6
    # Extra horizontal slack on top of QFontMetrics so the bubble width never
    # under-fits the rendered glyph run. Korean text via font fallback can
    # measure slightly narrower than it actually renders.
    WIDTH_SAFETY = 6

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

        self._text = ""
        self._anchor: Optional[QRect] = None
        self._tail_down = True
        self._font = QFont()
        self._font.setPointSize(9)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    # ---- public ----
    def show_text(self, text: str, ms: int, anchor: QRect) -> None:
        # Skip silently if a caller produces an empty string (e.g. an
        # edited-blank reminder, or a chatter line that resolved to "").
        # Without this guard the bubble would still show() at a stale
        # geometry with nothing painted — looks like "text never appeared".
        if not text or not text.strip():
            return
        # If a previous bubble's hide() is still mid-processing on the WM,
        # the new show() can land before the WM has fully released the layered
        # window — the resulting paint goes to a stale surface and the user
        # sees an empty bubble. Cancelling the pending hide_timer + forcing
        # the widget hidden synchronously gets us into a clean state first.
        self._hide_timer.stop()
        if self.isVisible() and self._text != text:
            # Cheaper than full hide/show — just invalidate the current
            # paint so the new text replaces whatever was rendered.
            self._text = text
            self._anchor = QRect(anchor)
            self._recompute_geometry()
            self.raise_()
            self.repaint()
            self._hide_timer.start(ms)
            return

        self._text = text
        self._anchor = QRect(anchor)
        self._recompute_geometry()
        self.show()
        self.raise_()
        # Two paint passes: synchronous (immediate) + deferred-after-event-loop
        # (catches the Windows layered-window case where the sync paint lands
        # before the show event has propagated to the WM).
        self.repaint()
        QTimer.singleShot(0, self._post_show_repaint)
        self._hide_timer.start(ms)

    def _post_show_repaint(self) -> None:
        """Fires on the next event-loop tick after show_text. Re-raises and
        repaints so the bubble survives Z-order shuffles caused by other
        always-on-top windows (MainPanel, popups, the wild encounter)."""
        if not self.isVisible() or not self._text:
            return
        self.raise_()
        self.update()

    def update_anchor(self, anchor: QRect) -> None:
        """Re-position over the buddy without changing text or timing."""
        if not self.isVisible():
            return
        self._anchor = QRect(anchor)
        self._recompute_geometry()

    # ---- internal ----
    def _measure(self, text: str) -> tuple[int, int]:
        """Return the (width, height) the rendered text will occupy.

        We always go through `boundingRect` with the same TextWordWrap flag
        that `paintEvent` uses — that way the bubble's geometry exactly
        matches what `drawText` actually produces, including any wraps. The
        old fast-path used `horizontalAdvance` for one-line text but that
        measurement disagreed with the rendering when font fallback kicked
        in (Korean glyphs), so the second wrapped line landed outside the
        bubble and looked like the message was 'cut off'."""
        fm = QFontMetrics(self._font)
        avail = self.MAX_TEXT_WIDTH - 2 * self.PAD_X
        br = fm.boundingRect(QRect(0, 0, avail, 10_000),
                             Qt.TextWordWrap, text)
        # Width safety: add a few pixels so even a slight render-vs-measure
        # mismatch can't push the last glyph past the right edge.
        return br.width() + self.WIDTH_SAFETY, br.height()

    def _recompute_geometry(self) -> None:
        if not self._text or self._anchor is None:
            return
        tw, th = self._measure(self._text)
        w = tw + 2 * self.PAD_X
        h = th + 2 * self.PAD_Y + self.TAIL_H

        # Clamp inside the screen that ACTUALLY contains the buddy. Using
        # primaryScreen here would teleport the bubble to monitor #1 when
        # the buddy lives on a secondary monitor — looks like "text didn't
        # show up" because it appears far from where the user is looking.
        anchor_center = self._anchor.center()
        screen_obj = (QGuiApplication.screenAt(anchor_center)
                      or QGuiApplication.primaryScreen())
        screen = screen_obj.availableGeometry()
        cx = anchor_center.x()
        x = max(screen.left() + 4, min(cx - w // 2, screen.right() - w - 4))

        y_above = self._anchor.top() - h - self.GAP
        y_below = self._anchor.bottom() + self.GAP
        if y_above >= screen.top() + 4:
            y = y_above
            self._tail_down = True
        else:
            y = min(y_below, screen.bottom() - h - 4)
            self._tail_down = False

        self.setGeometry(x, y, w, h)
        self.update()

    # ---- paint ----
    def paintEvent(self, _e) -> None:  # noqa: N802
        if not self._text:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        if self._tail_down:
            body = QRect(0, 0, self.width(), self.height() - self.TAIL_H)
        else:
            body = QRect(0, self.TAIL_H, self.width(),
                         self.height() - self.TAIL_H)

        p.setBrush(QColor(255, 255, 255, 238))
        p.setPen(QPen(QColor(70, 70, 70), 1))
        p.drawRoundedRect(body, 10, 10)

        # Tail
        if self._anchor is not None:
            cx = max(body.left() + 14,
                     min(self._anchor.center().x() - self.x(),
                         body.right() - 14))
        else:
            cx = self.width() // 2

        if self._tail_down:
            tail = QPolygonF([
                QPointF(cx - 6, body.bottom()),
                QPointF(cx + 6, body.bottom()),
                QPointF(cx,     body.bottom() + self.TAIL_H),
            ])
        else:
            tail = QPolygonF([
                QPointF(cx - 6, body.top()),
                QPointF(cx + 6, body.top()),
                QPointF(cx,     body.top() - self.TAIL_H),
            ])
        # Fill then stroke for clean junction with body border
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 238))
        p.drawPolygon(tail)
        p.setPen(QPen(QColor(70, 70, 70), 1))
        # Draw the two slanted edges of the tail only
        if self._tail_down:
            p.drawLine(QPointF(cx - 6, body.bottom()),
                       QPointF(cx,     body.bottom() + self.TAIL_H))
            p.drawLine(QPointF(cx + 6, body.bottom()),
                       QPointF(cx,     body.bottom() + self.TAIL_H))
        else:
            p.drawLine(QPointF(cx - 6, body.top()),
                       QPointF(cx,     body.top() - self.TAIL_H))
            p.drawLine(QPointF(cx + 6, body.top()),
                       QPointF(cx,     body.top() - self.TAIL_H))

        # Text
        p.setPen(QColor(30, 30, 30))
        p.setFont(self._font)
        text_rect = body.adjusted(self.PAD_X, self.PAD_Y, -self.PAD_X, -self.PAD_Y)
        p.drawText(text_rect, Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap,
                   self._text)
        p.end()
