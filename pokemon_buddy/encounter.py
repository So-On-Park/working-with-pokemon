"""Wild-encounter manager. Polls on a timer; spawns at most one wild
Pokemon at a time, respecting probability + cooldown gates. Silent on
offline failure. When the user clicks the wild Pokemon, the manager
orchestrates the throw → shake → resolve sequence."""

from __future__ import annotations

import logging
import random
import time
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget

from .config import (
    CATCH_RATE,
    DEFAULT_SPRITE_STYLE,
    ENCOUNTER_CHECK_MS,
    ENCOUNTER_COOLDOWN_S,
    ENCOUNTER_DEX_RANGE,
    ENCOUNTER_PROBABILITY,
    RARE_PROBABILITY,
)
from .custom_pokemon import is_custom as is_custom_pokemon
from .custom_pokemon import list_dex_ids as list_custom_dex_ids
from .encounter_window import WildPokemonWindow
from .pokeball import Pokeball
from .pokemon_names import fallback_name, fetch_name
from .sprites import get_buddy_sprite_with_fallback
from .star_burst import StarBurst
from .state import Store
from .windows_state import is_screen_locked

log = logging.getLogger(__name__)


class EncounterManager(QObject):
    spawned = Signal(object)              # WildPokemonWindow — for debugging / hooks
    caught = Signal(int, str, bool, str)  # dex_id, base name, is_rare, ball_key
    fled = Signal(int, str, bool)
    skipped = Signal(str)                 # reason
    needs_pokeball = Signal()             # user clicked but bag is empty

    def __init__(self, store: Store, buddy_widget: QWidget,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self.buddy_widget = buddy_widget
        self._active: Optional[WildPokemonWindow] = None
        self._ball: Optional[Pokeball] = None
        self._burst: Optional[StarBurst] = None
        # Set true when this catch attempt is using a pre-armed master ball
        # — bypasses the regular catch_rate roll for a guaranteed success.
        self._master_ball_active = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    # ---- lifecycle ----
    def start(self) -> None:
        self._timer.start(ENCOUNTER_CHECK_MS)

    def stop(self) -> None:
        self._timer.stop()
        self._cleanup()

    def force_spawn(self) -> None:
        self._spawn(ignore_cooldown=True)

    def request_auto_catch(self) -> None:
        """Trigger a catch attempt programmatically (used by the 명포수 skill).
        Same path as a user click; no-op if nothing is active or a throw is
        already in flight."""
        if self._active is None or self._ball is not None:
            return
        self._on_pokemon_clicked()

    # ---- polling ----
    def _tick(self) -> None:
        # Don't spawn wild Pokemon while the workstation is locked — the
        # user can't see them and they'd just auto-flee silently.
        if is_screen_locked():
            return
        if random.random() >= ENCOUNTER_PROBABILITY:
            return
        self._spawn(ignore_cooldown=False)

    def _spawn(self, ignore_cooldown: bool) -> bool:
        if self._active is not None:
            self.skipped.emit("already-active")
            return False

        if not ignore_cooldown:
            last = self.store.get_meta("last_encounter_at", "0") or "0"
            try:
                last_f = float(last)
            except ValueError:
                last_f = 0.0
            if time.time() - last_f < ENCOUNTER_COOLDOWN_S:
                self.skipped.emit("cooldown")
                return False

        lo, hi = ENCOUNTER_DEX_RANGE
        style = (self.store.get_meta("sprite_style", DEFAULT_SPRITE_STYLE)
                 or DEFAULT_SPRITE_STYLE)
        # Resolve the user-selected style back to one of the two supported
        # modes — old "*_shiny" style settings collapse to their base now
        # that rare is a per-Pokemon attribute.
        if style not in ("bw", "showdown"):
            style = "bw" if style.startswith("bw") else "showdown"

        # Spawn pool: vanilla dex range + any user-registered customs.
        pool = list(range(lo, hi + 1)) + list_custom_dex_ids()
        dex_id = random.choice(pool)
        # Custom pokemon don't have rare/shiny art — skip the rare roll for them.
        is_rare = (not is_custom_pokemon(dex_id)
                   and random.random() < RARE_PROBABILITY)

        sprite = get_buddy_sprite_with_fallback(style, dex_id, is_rare)
        if sprite is None:
            for _ in range(5):
                dex_id = random.choice(pool)
                is_rare = (not is_custom_pokemon(dex_id)
                           and random.random() < RARE_PROBABILITY)
                sprite = get_buddy_sprite_with_fallback(style, dex_id, is_rare)
                if sprite is not None:
                    break
        if sprite is None:
            self.skipped.emit("no-sprite-offline")
            return False

        name = fetch_name(dex_id) or fallback_name(dex_id)

        win = WildPokemonWindow(dex_id, name, sprite, is_rare=is_rare)
        screen = QGuiApplication.primaryScreen()
        geo = screen.availableGeometry() if screen else self.buddy_widget.geometry()
        win.place_random(geo, self.buddy_widget.frameGeometry())

        win.clicked.connect(self._on_pokemon_clicked)
        win.flee_timeout.connect(self._on_pokemon_fled_timeout)
        win.destroyed.connect(self._on_destroyed)

        self._active = win
        win.show()
        self.spawned.emit(win)
        self.store.set_meta("last_encounter_at", str(time.time()))
        return True

    # ---- catch sequence ----
    def _on_pokemon_clicked(self) -> None:
        if self._active is None:
            return
        target = self._active

        # Master ball pre-armed? Skip the regular pokeball check + guarantee
        # the catch. The flag is consumed at click time so the user knows
        # exactly when their master ball is spent.
        if self.store.get_meta("master_ball_pending") == "1":
            self.store.set_meta("master_ball_pending", "0")
            self._master_ball_active = True
        else:
            self._master_ball_active = False
            ball_key = self.store.first_available_of_kind("pokeball")
            if ball_key is None or not self.store.consume_item(ball_key, 1):
                # Re-arm the click so the user can try again once they pick
                # up a Pokeball (rather than blowing the encounter away).
                target.allow_retry()
                self.needs_pokeball.emit()
                return

        start = self.buddy_widget.frameGeometry().center()
        end = target.frameGeometry().center()

        ball = Pokeball()
        self._ball = ball
        ball.fly_to(start, end, on_arrived=lambda: self._on_ball_arrived(target))

    def _on_ball_arrived(self, target: WildPokemonWindow) -> None:
        # Pokemon shrinks into the ball
        target.absorb_into_ball(on_done=self._on_pokemon_absorbed)

    def _on_pokemon_absorbed(self) -> None:
        # Master ball guarantees the catch; otherwise roll against CATCH_RATE.
        if self._master_ball_active:
            success = True
        else:
            success = random.random() < CATCH_RATE
        if self._ball is None:
            return
        self._ball.shake(on_done=lambda: self._resolve_catch(success))

    def _resolve_catch(self, success: bool) -> None:
        if self._ball is None or self._active is None:
            return
        target = self._active
        ball = self._ball
        if success:
            # Star burst at the ball's location, then the ball flies back
            # to the buddy. The wild Pokemon stays hidden (absorbed).
            burst_center = ball.frameGeometry().center()
            self._burst = StarBurst()
            self._burst.play_at(
                burst_center,
                on_done=lambda: self._after_star_burst(target),
            )
        else:
            ball.finish_fail(on_done=lambda: self._on_catch_failed(target))

    def _after_star_burst(self, target: WildPokemonWindow) -> None:
        """Stars finished — fly the ball home to the buddy, then emit the
        caught signal."""
        if self._ball is None or self._active is None:
            # Cleanup happened mid-sequence (encounter cancelled?). Bail.
            return
        buddy_center = self.buddy_widget.frameGeometry().center()
        self._ball.return_to(
            buddy_center,
            on_done=lambda: self._on_catch_success(target),
        )

    def _on_catch_success(self, target: WildPokemonWindow) -> None:
        dex_id, name, is_rare = target.dex_id, target.name, target.is_rare
        ball_key = ("special.master-ball" if self._master_ball_active
                    else "pokeball.basic")
        self._cleanup()
        self.caught.emit(dex_id, name, is_rare, ball_key)

    def _on_catch_failed(self, target: WildPokemonWindow) -> None:
        # The Pokemon bursts back out and escapes.
        def then_escape() -> None:
            target.escape_off_screen(
                on_done=lambda: self._on_escape_complete(target)
            )
        target.reappear(on_done=then_escape)

    def _on_escape_complete(self, target: WildPokemonWindow) -> None:
        dex_id, name, is_rare = target.dex_id, target.name, target.is_rare
        self._cleanup()
        self.fled.emit(dex_id, name, is_rare)

    # ---- timeout flee (user ignored the encounter) ----
    def _on_pokemon_fled_timeout(self) -> None:
        if self._active is None:
            return
        target = self._active
        dex_id, name, is_rare = target.dex_id, target.name, target.is_rare
        target.escape_off_screen(
            on_done=lambda: (self._cleanup(),
                             self.fled.emit(dex_id, name, is_rare))
        )

    # ---- cleanup ----
    def _cleanup(self) -> None:
        if self._burst is not None:
            self._burst.hide()
            self._burst.deleteLater()
            self._burst = None
        if self._ball is not None:
            self._ball.hide()
            self._ball.deleteLater()
            self._ball = None
        if self._active is not None:
            self._active.hide()
            self._active.deleteLater()
            self._active = None

    def _on_destroyed(self, *_: object) -> None:
        # Backstop if something closes the wild window outside our control.
        self._active = None
