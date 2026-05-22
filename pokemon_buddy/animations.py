"""Action animations driven by sprite-level 2D transforms.

Animations are all one-shot — they're triggered by an explicit action (feed,
click, level up, …) and revert to Idle when finished. Idle does no per-tick
work; the GIF's own frame redraws keep the sprite alive."""

from __future__ import annotations

import math
import time
from typing import Optional

from PySide6.QtCore import QEasingCurve, QObject, Qt, QTimer, QVariantAnimation

from .config import (
    ANIM_TICK_MS,
    EAT_MAX_ROT_DEG,
    HAPPY_MAX_SCALE,
    SAD_TILT_DEG,
    SURPRISED_MAX_SCALE,
    TRAIN_NOD_DEG,
)
from .sprite_widget import SpriteWidget


class _Anim:
    name: str = ""
    duration_ms: int = 0  # -1 for persistent

    def compute(self, t_ms: int, w: SpriteWidget) -> None:
        raise NotImplementedError


class _Idle(_Anim):
    name = "idle"
    duration_ms = -1

    def compute(self, t_ms: int, w: SpriteWidget) -> None:
        # Identity — handled by reset_transform on transition. No per-tick work.
        pass


class _Happy(_Anim):
    name = "happy"
    duration_ms = 600

    def compute(self, t_ms: int, w: SpriteWidget) -> None:
        if t_ms < 200:
            f = t_ms / 200.0
            ease = 1.0 - (1.0 - f) ** 2
            scale = 1.0 + (HAPPY_MAX_SCALE - 1.0) * ease
            dy = -8.0 * ease
        elif t_ms < 400:
            f = (t_ms - 200) / 200.0
            scale = HAPPY_MAX_SCALE - (HAPPY_MAX_SCALE - 0.92) * f
            dy = -8.0 + 12.0 * f
        else:
            f = (t_ms - 400) / 200.0
            scale = 0.92 + 0.08 * f
            dy = 4.0 - 4.0 * f
        w.set_transform(scale=scale, dy=dy)


class _Eat(_Anim):
    name = "eat"
    duration_ms = 1500

    def compute(self, t_ms: int, w: SpriteWidget) -> None:
        sec = t_ms / 1000.0
        rot = math.sin(sec * 12.0) * EAT_MAX_ROT_DEG
        # gentle fade at the tail so we land softly on identity
        if t_ms > 1200:
            rot *= max(0.0, (1500 - t_ms) / 300.0)
        # tiny vertical bob — like chewing
        dy = abs(math.sin(sec * 6.0)) * 2.0
        w.set_transform(rotation_deg=rot, dy=dy)


class _Train(_Anim):
    name = "train"
    duration_ms = 1400

    def compute(self, t_ms: int, w: SpriteWidget) -> None:
        if t_ms < 900:
            sec = t_ms / 1000.0
            rot = abs(math.sin(sec * 6.5)) * TRAIN_NOD_DEG
            w.set_transform(rotation_deg=rot, dy=rot * 0.4)
        else:
            f = (t_ms - 900) / 500.0
            # chest puff / proud pose
            w.set_transform(scale=1.0 + 0.08 * f, dy=-3.0 * f)


class _Surprised(_Anim):
    name = "surprised"
    duration_ms = 500

    def compute(self, t_ms: int, w: SpriteWidget) -> None:
        if t_ms < 150:
            f = t_ms / 150.0
            scale = 1.0 + (SURPRISED_MAX_SCALE - 1.0) * f
            dy = -6.0 * f
        elif t_ms < 300:
            scale = SURPRISED_MAX_SCALE
            dy = -6.0
        else:
            f = (t_ms - 300) / 200.0
            scale = SURPRISED_MAX_SCALE - (SURPRISED_MAX_SCALE - 1.0) * f
            dy = -6.0 + 6.0 * f
        w.set_transform(scale=scale, dy=dy)


class _Sad(_Anim):
    name = "sad"
    duration_ms = 1500

    def compute(self, t_ms: int, w: SpriteWidget) -> None:
        if t_ms < 500:
            f = t_ms / 500.0
        elif t_ms > 1000:
            f = max(0.0, (1500 - t_ms) / 500.0)
        else:
            f = 1.0
        w.set_transform(rotation_deg=SAD_TILT_DEG * f, dy=3.0 * f)


ANIMATIONS: dict[str, type[_Anim]] = {
    "idle": _Idle,
    "happy": _Happy,
    "eat": _Eat,
    "train": _Train,
    "surprised": _Surprised,
    "sad": _Sad,
}


class AnimationEngine(QObject):
    """Drives the SpriteWidget transform. One-shots take priority over the
    persistent track. Returning to Idle resets the transform to identity."""

    def __init__(self, sprite_widget: SpriteWidget,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._w = sprite_widget
        self._one_shot: Optional[_Anim] = None
        self._one_shot_t0: float = 0.0
        self._persistent: _Anim = _Idle()
        self._persistent_t0: float = time.time()

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.setInterval(ANIM_TICK_MS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # ---- API ----
    def play(self, name: str) -> None:
        """Schedule a one-shot animation. No-op for unknown names."""
        cls = ANIMATIONS.get(name)
        if cls is None or cls is _Idle:
            return
        anim = cls()
        if anim.duration_ms < 0:
            # persistent — route through set_persistent
            self.set_persistent(name)
            return
        self._one_shot = anim
        self._one_shot_t0 = time.time()

    def play_halo(self, duration_ms: int = 1500) -> None:
        """Trigger a one-shot golden glow behind the sprite — used on
        level-up. Drives `SpriteWidget.halo_alpha` / `halo_scale` through
        a smooth sin() bell curve so the halo fades in, peaks, and fades
        out without any continuous motion lingering afterward."""
        anim = QVariantAnimation(self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(duration_ms)
        anim.setEasingCurve(QEasingCurve.Linear)
        anim.valueChanged.connect(self._on_halo_progress)
        anim.finished.connect(self._on_halo_done)
        anim.start()
        # Hold a ref so Qt doesn't GC the animation mid-run.
        self._halo_anim = anim

    def _on_halo_progress(self, t) -> None:
        t = float(t)
        # sin(πt) gives a smooth 0 → 1 → 0 over t∈[0,1].
        bell = math.sin(t * math.pi)
        self._w.halo_alpha = bell
        # Subtle scale pulse (1.0 → 1.1 → 1.0). Small enough not to read
        # as 'movement' but enough to make the halo feel alive.
        self._w.halo_scale = 1.0 + 0.10 * bell
        self._w.update()

    def _on_halo_done(self) -> None:
        self._w.halo_alpha = 0.0
        self._w.halo_scale = 1.0
        self._w.update()

    def set_persistent(self, name: str) -> None:
        cls = ANIMATIONS.get(name)
        if cls is None:
            return
        # If already this kind of animation, leave it alone — preserves phase.
        if isinstance(self._persistent, cls):
            return
        self._persistent = cls()
        self._persistent_t0 = time.time()
        if isinstance(self._persistent, _Idle):
            self._w.reset_transform()

    def clear_persistent(self) -> None:
        self.set_persistent("idle")

    # ---- driver ----
    def _tick(self) -> None:
        now = time.time()

        if self._one_shot is not None:
            t_ms = int((now - self._one_shot_t0) * 1000)
            if t_ms < self._one_shot.duration_ms:
                self._one_shot.compute(t_ms, self._w)
                return
            # one-shot finished — clean up and fall through to persistent
            self._one_shot = None
            self._persistent_t0 = now
            if isinstance(self._persistent, _Idle):
                self._w.reset_transform()
                return

        if isinstance(self._persistent, _Idle):
            # nothing to do — GIF redraws itself via frameChanged
            return

        t_ms = int((now - self._persistent_t0) * 1000)
        self._persistent.compute(t_ms, self._w)
