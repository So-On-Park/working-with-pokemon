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
    ITEM_DROP_SIZE_SMALL_PX,
    MAGNETIZE_DELAY_MS,
    MAGNETIZE_TRAVEL_MS,
    SKILL_DROP_AUTO_FADE_MS,
    SKILL_DROP_PROBABILITY,
)
from .items import (
    DROP_WEIGHTS,
    ItemDef,
    ItemKind,
    SPECIAL_DROP_WEIGHTS,
    find as find_item,
    items_of,
)
from .pokeball import make_pokeball_pixmap
from .sprites import get_item_sprite
from .state import Store
from .windows_state import is_screen_locked

log = logging.getLogger(__name__)


def drop_size_for(kind: ItemKind) -> int:
    """On-screen drop size by kind. Food / toy / pokeball are small; special
    + skill keep the larger icon so their game-art reads clearly."""
    if kind in (ItemKind.FOOD, ItemKind.TOY, ItemKind.POKEBALL):
        return ITEM_DROP_SIZE_SMALL_PX
    return ITEM_DROP_SIZE_PX


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
    magnetized = Signal()  # arrived at a collector buddy → auto-collect

    def __init__(self, item: ItemDef, parent: QWidget | None = None,
                 auto_fade_ms: int = ITEM_DROP_AUTO_FADE_MS) -> None:
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
        size = drop_size_for(item.kind)
        self.setFixedSize(size, size)

        label = QLabel(self)
        label.setAlignment(Qt.AlignCenter)
        label.setGeometry(0, 0, size, size)
        label.setStyleSheet("background: transparent;")
        # Three visual paths: pokeballs use the painted icon, items with a
        # PokeAPI slug load their sprite, everything else uses emoji.
        icon_pm = None
        if item.kind == ItemKind.POKEBALL:
            icon_pm = make_pokeball_pixmap(size - 4)
        elif item.slug:
            sprite_path = get_item_sprite(item.slug)
            if sprite_path is not None:
                from PySide6.QtGui import QPixmap
                pm = QPixmap(str(sprite_path))
                if not pm.isNull():
                    icon_pm = pm.scaled(
                        size - 4, size - 4,
                        Qt.KeepAspectRatio, Qt.SmoothTransformation,
                    )
        if icon_pm is not None:
            label.setPixmap(icon_pm)
        else:
            label.setText(item.emoji)
            font = QFont()
            font.setPointSize(max(14, int(size * 0.5)))
            label.setFont(font)
        # Let clicks fall through the label to the window — we handle them in
        # the window's mousePressEvent so the whole 44×44 area is the target.
        label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.setToolTip(item.label)

        self._auto_fade = QTimer(self)
        self._auto_fade.setSingleShot(True)
        self._auto_fade.timeout.connect(self._on_auto_fade)
        self._auto_fade.start(auto_fade_ms)

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

    # ---- magnetize (수집광) ----
    def magnet_to(self, target_center: QPoint) -> bool:
        """Slide this drop toward `target_center` (a buddy that knows 수집광),
        then emit `magnetized` so the manager auto-collects it. No-op if the
        drop was already clicked/expired. Returns True if travel started."""
        if self._resolved:
            return False
        self._resolved = True
        self._auto_fade.stop()
        if hasattr(self, "_sway"):
            self._sway.stop()
        dest = QPoint(target_center.x() - self.width() // 2,
                      target_center.y() - self.height() // 2)
        anim = QPropertyAnimation(self, b"pos", self)
        anim.setStartValue(self.pos())
        anim.setEndValue(dest)
        anim.setDuration(MAGNETIZE_TRAVEL_MS)
        anim.setEasingCurve(QEasingCurve.InCubic)
        anim.finished.connect(self.magnetized.emit)
        anim.start()
        self._magnet_anim = anim
        return True

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
    collected = Signal(str)         # item_key (manual click → primary)
    magnet_collected = Signal(str, object)  # item_key, target QPoint (수집광)
    skipped = Signal(str)

    def __init__(self, store: Store, buddy_widget: QWidget,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self.buddy_widget = buddy_widget
        self._active: List[ItemDropWindow] = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._enabled = True
        # Set by BuddyApp: returns a list of QPoint centers for party members
        # that know 수집광. Drops drift to the nearest one shortly after they
        # appear. None / empty list = no magnet behaviour.
        self.magnet_provider = None

    # ---- lifecycle ----
    def start(self) -> None:
        self._timer.start(ITEM_DROP_CHECK_MS)
        # Run an early initial roll so the user sees activity soon.
        QTimer.singleShot(15_000, self._tick)

    def stop(self) -> None:
        self._timer.stop()
        self._clear_active()

    def _clear_active(self) -> None:
        for w in list(self._active):
            w.hide()
            w.deleteLater()
        self._active.clear()

    def set_enabled(self, enabled: bool) -> None:
        """User toggle (화면 아이템 표시). When off, stop spawning and clear
        anything currently on screen. Polling timer keeps running so flipping
        it back on resumes immediately."""
        self._enabled = bool(enabled)
        if not self._enabled:
            self._clear_active()

    def force_spawn(self) -> bool:
        return self._spawn(ignore_cooldown=True)

    # ---- polling ----
    def _tick(self) -> None:
        # Locked screen → no drops; the user won't see them and they'd
        # just expire silently. Also honour the user's display toggle.
        if is_screen_locked() or not self._enabled:
            return
        # Independent rare roll for a skill teaching scroll (두루마리).
        if random.random() < SKILL_DROP_PROBABILITY:
            scroll = find_item("skill.collector")
            if scroll is not None and self._spawn(ignore_cooldown=False,
                                                  item=scroll):
                return
        if random.random() >= ITEM_DROP_PROBABILITY:
            return
        self._spawn(ignore_cooldown=False)

    def _spawn(self, ignore_cooldown: bool,
               item: Optional[ItemDef] = None) -> bool:
        if not self._enabled:
            return False
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

        if item is None:
            item = _pick_random_item()
        fade = (SKILL_DROP_AUTO_FADE_MS if item.kind == ItemKind.SKILL
                else ITEM_DROP_AUTO_FADE_MS)
        win = ItemDropWindow(item, auto_fade_ms=fade)

        # Place on the screen that contains the buddy, not always primary.
        anchor = self.buddy_widget.frameGeometry()
        screen_obj = (QGuiApplication.screenAt(anchor.center())
                      or QGuiApplication.primaryScreen())
        geo = screen_obj.availableGeometry()
        win.place_random(geo, anchor)

        win.clicked.connect(lambda w=win: self._on_collected(w))
        win.expired.connect(lambda w=win: self._on_expired(w))
        win.magnetized.connect(lambda w=win: self._on_magnet_arrived(w))

        self._active.append(win)
        win.show()
        self.spawned.emit(win)
        self.store.set_meta("last_item_drop_at", str(time.time()))
        # A 수집광 buddy reels the drop in shortly after it lands.
        QTimer.singleShot(MAGNETIZE_DELAY_MS, lambda w=win: self._try_magnet(w))
        return True

    # ---- magnetize ----
    def _try_magnet(self, win: ItemDropWindow) -> None:
        if win not in self._active or win._resolved:
            return
        if self.magnet_provider is None:
            return
        try:
            targets = self.magnet_provider() or []
        except Exception:  # noqa: BLE001
            targets = []
        if not targets:
            return
        # Party-order priority: the provider returns 수집광 buddies in slot
        # order (1 → 2 → 3), so the first one reels it in.
        target = targets[0]
        win._magnet_target = target
        win.magnet_to(target)

    def _on_magnet_arrived(self, win: ItemDropWindow) -> None:
        key = win.item.key
        target = getattr(win, "_magnet_target", None)
        self._cleanup(win)
        self.magnet_collected.emit(key, target)

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
