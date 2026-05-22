"""Item drop system — fruits / toys / pokeballs appear on screen for the
user to click and collect into their bag.

Each drop is its own frameless transparent floating window showing the
item's emoji. The manager limits how many are active at once, picks an
item kind by weight, and respects a cooldown between drops. Items are
intentionally STATIC — no bob, no sparkle — to avoid adding peripheral
motion (the buddy owner is motion-sensitive).
"""

from __future__ import annotations

import logging
import random
import time
from typing import List, Optional

from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import QLabel, QWidget

from .config import (
    ITEM_DROP_AUTO_FADE_MS,
    ITEM_DROP_CHECK_MS,
    ITEM_DROP_COOLDOWN_S,
    ITEM_DROP_MAX_ACTIVE,
    ITEM_DROP_PROBABILITY,
    ITEM_DROP_SIZE_PX,
)
from .items import (
    DROP_WEIGHTS,
    ItemDef,
    ItemKind,
    SPECIAL_DROP_WEIGHTS,
    items_of,
)
from .pokeball import make_pokeball_pixmap
from .sprites import get_item_sprite
from .state import Store
from .windows_state import is_screen_locked

log = logging.getLogger(__name__)


def _pick_random_item() -> ItemDef:
    kinds = list(DROP_WEIGHTS.keys())
    weights = [DROP_WEIGHTS[k] for k in kinds]
    chosen_kind: ItemKind = random.choices(kinds, weights=weights, k=1)[0]
    pool = items_of(chosen_kind)
    if chosen_kind == ItemKind.SPECIAL:
        # SPECIAL subtypes have per-item weights so master ball stays rare
        # while potions are relatively common.
        sub = [SPECIAL_DROP_WEIGHTS.get(it.key, 10) for it in pool]
        return random.choices(pool, weights=sub, k=1)[0]
    return random.choice(pool)


class ItemDropWindow(QWidget):
    """A single dropped item. Click to collect; auto-fades after a timeout
    if the user ignores it."""

    clicked = Signal()
    expired = Signal()

    def __init__(self, item: ItemDef, parent: QWidget | None = None) -> None:
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self.item = item
        self._resolved = False
        self.setFixedSize(ITEM_DROP_SIZE_PX, ITEM_DROP_SIZE_PX)

        label = QLabel(self)
        label.setAlignment(Qt.AlignCenter)
        label.setGeometry(0, 0, ITEM_DROP_SIZE_PX, ITEM_DROP_SIZE_PX)
        label.setStyleSheet("background: transparent;")
        # Three visual paths: pokeballs use the painted icon, items with a
        # PokeAPI slug load their sprite, everything else uses emoji.
        icon_pm = None
        if item.kind == ItemKind.POKEBALL:
            icon_pm = make_pokeball_pixmap(ITEM_DROP_SIZE_PX - 4)
        elif item.slug:
            sprite_path = get_item_sprite(item.slug)
            if sprite_path is not None:
                from PySide6.QtGui import QPixmap
                pm = QPixmap(str(sprite_path))
                if not pm.isNull():
                    icon_pm = pm.scaled(
                        ITEM_DROP_SIZE_PX - 4, ITEM_DROP_SIZE_PX - 4,
                        Qt.KeepAspectRatio, Qt.SmoothTransformation,
                    )
        if icon_pm is not None:
            label.setPixmap(icon_pm)
        else:
            label.setText(item.emoji)
            font = QFont()
            font.setPointSize(22)
            label.setFont(font)
        # Let clicks fall through the label to the window — we handle them in
        # the window's mousePressEvent so the whole 44×44 area is the target.
        label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.setToolTip(item.label)

        self._auto_fade = QTimer(self)
        self._auto_fade.setSingleShot(True)
        self._auto_fade.timeout.connect(self._on_auto_fade)
        self._auto_fade.start(ITEM_DROP_AUTO_FADE_MS)

        # Subtle horizontal sway on the label only — the widget (and its
        # click-target rect) stays put. Animation ranges ±2px and runs at
        # InOutSine for a slow breathing feel. Each drop starts at a random
        # offset within the cycle so multiple drops don't sway in lockstep.
        self._sway = QPropertyAnimation(label, b"pos", self)
        self._sway.setStartValue(QPoint(-2, 0))
        self._sway.setEndValue(QPoint(2, 0))
        self._sway.setDuration(1400)
        self._sway.setEasingCurve(QEasingCurve.InOutSine)
        self._sway.setLoopCount(-1)
        self._sway.setCurrentTime(random.randint(0, 1400))
        self._sway.start()

    # ---- placement ----
    def place_random(self, screen_geo, avoid_rect) -> None:
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
        self.move(min_x, min_y)

    # ---- mouse ----
    def mousePressEvent(self, ev) -> None:  # noqa: N802
        if self._resolved:
            return
        if ev.button() == Qt.LeftButton:
            self._resolved = True
            self._auto_fade.stop()
            self.clicked.emit()

    # ---- fade out ----
    def fade_and_close(self, on_done) -> None:
        # Stop the sway so it doesn't keep nudging the label while we fade.
        if hasattr(self, "_sway"):
            self._sway.stop()
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setStartValue(self.windowOpacity() or 1.0)
        anim.setEndValue(0.0)
        anim.setDuration(400)
        anim.finished.connect(on_done)
        anim.start()
        self._fade_anim = anim

    def _on_auto_fade(self) -> None:
        if self._resolved:
            return
        self._resolved = True
        self.expired.emit()


class ItemDropManager(QObject):
    """Drives item spawns. Emits `collected(item_key)` when the user picks
    an item up; the app routes that to `Store.add_item`."""

    spawned = Signal(object)        # ItemDropWindow
    collected = Signal(str)         # item_key
    skipped = Signal(str)

    def __init__(self, store: Store, buddy_widget: QWidget,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self.buddy_widget = buddy_widget
        self._active: List[ItemDropWindow] = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    # ---- lifecycle ----
    def start(self) -> None:
        self._timer.start(ITEM_DROP_CHECK_MS)
        # Run an early initial roll so the user sees activity soon.
        QTimer.singleShot(15_000, self._tick)

    def stop(self) -> None:
        self._timer.stop()
        for w in list(self._active):
            w.hide()
            w.deleteLater()
        self._active.clear()

    def force_spawn(self) -> bool:
        return self._spawn(ignore_cooldown=True)

    # ---- polling ----
    def _tick(self) -> None:
        # Locked screen → no drops; the user won't see them and they'd
        # just expire silently.
        if is_screen_locked():
            return
        if random.random() >= ITEM_DROP_PROBABILITY:
            return
        self._spawn(ignore_cooldown=False)

    def _spawn(self, ignore_cooldown: bool) -> bool:
        if len(self._active) >= ITEM_DROP_MAX_ACTIVE:
            self.skipped.emit("max-active")
            return False

        if not ignore_cooldown:
            last = self.store.get_meta("last_item_drop_at", "0") or "0"
            try:
                last_f = float(last)
            except ValueError:
                last_f = 0.0
            if time.time() - last_f < ITEM_DROP_COOLDOWN_S:
                self.skipped.emit("cooldown")
                return False

        item = _pick_random_item()
        win = ItemDropWindow(item)

        # Place on the screen that contains the buddy, not always primary.
        anchor = self.buddy_widget.frameGeometry()
        screen_obj = (QGuiApplication.screenAt(anchor.center())
                      or QGuiApplication.primaryScreen())
        geo = screen_obj.availableGeometry()
        win.place_random(geo, anchor)

        win.clicked.connect(lambda w=win: self._on_collected(w))
        win.expired.connect(lambda w=win: self._on_expired(w))

        self._active.append(win)
        win.show()
        self.spawned.emit(win)
        self.store.set_meta("last_item_drop_at", str(time.time()))
        return True

    def _on_collected(self, win: ItemDropWindow) -> None:
        key = win.item.key
        win.fade_and_close(lambda w=win: self._cleanup(w))
        self.collected.emit(key)

    def _on_expired(self, win: ItemDropWindow) -> None:
        win.fade_and_close(lambda w=win: self._cleanup(w))

    def _cleanup(self, win: ItemDropWindow) -> None:
        if win in self._active:
            self._active.remove(win)
        win.hide()
        win.deleteLater()
