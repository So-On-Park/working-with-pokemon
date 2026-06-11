"""One buddy's complete on-screen presence — window, sprite, animations,
speech bubble, chatter, and per-action gameplay logic.

`BuddyApp` keeps a list of these (up to 3, one per party slot). Each
agent is independent: its own QWindow, its own AnimationEngine instance,
its own ChatterEngine, its own last_passive_at timer. Wild encounters,
reminders, and scheduled greetings stay with the *primary* (slot 0)
agent — handled by BuddyApp — so the buddy you put in front doesn't get
drowned out by the companions in slot 1 / 2."""

from __future__ import annotations

import time
from typing import Optional

from PySide6.QtCore import QObject, Signal

from .animations import AnimationEngine
from .chatter import ChatterEngine
from .config import (
    FEED_EXP,
    FRIENDSHIP_FEED,
    FRIENDSHIP_LEVEL_UP,
    FRIENDSHIP_PET,
    FRIENDSHIP_PLAY,
    FRIENDSHIP_TRAIN,
    PASSIVE_EXP,
    PASSIVE_FRIENDSHIP_XP,
    PASSIVE_INTERVAL_S,
    PLAY_EXP,
    TRAIN_EXP,
)
from .items import ItemKind, find as find_item
from . import messages
from .pet_window import PetWindow
from .sprites import get_buddy_sprite_with_fallback
from .state import Buddy, Store


class BuddyAgent(QObject):
    """Owns the per-buddy widgets and runs the per-buddy game logic.
    Action methods are called by BuddyApp in response to popup choices or
    encounter-driven events. Level-up emits a signal so BuddyApp can show
    the (single, modal) evolution dialog."""

    leveled_up = Signal(object)          # self — for evolution prompts
    popup_requested = Signal(object, object)  # (agent, anchor_rect)
    pet_requested = Signal(object)       # agent

    def __init__(self, store: Store, buddy: Buddy, sprite_style: str, *,
                 slot_index: int, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self.buddy = buddy
        self.sprite_style = sprite_style
        self.slot_index = slot_index

        self.window = PetWindow()
        self._refresh_sprite()
        # Forward window signals up via our own signals so BuddyApp can
        # route them by agent.
        self.window.popup_requested.connect(
            lambda rect: self.popup_requested.emit(self, rect)
        )
        self.window.play_requested.connect(
            lambda: self.pet_requested.emit(self)
        )

        self.anim = AnimationEngine(self.window.sprite, parent=self.window)

        # Each buddy chatters independently — different personality → different
        # voice in the bubble. Daily greeting only fires for the primary slot
        # so the user doesn't get hit with three "다시 만나서 반가워" lines on
        # a single morning launch.
        self.chatter = ChatterEngine(
            store, lambda: self.buddy, parent=self.window,
        )
        self.chatter.chatter.connect(self._on_chatter)
        if slot_index == 0:
            self.chatter.daily_greeting.connect(self._on_daily_greeting)

        self._last_passive_at = time.time()
        self._restore_position()
        self.window.show()
        self.chatter.start()
        self._update_status()

    # ---- lifecycle ----
    def _restore_position(self) -> None:
        """Per-buddy saved coordinates, falling back to a slot-offset
        default position so newly-added party members don't all land on
        top of the existing buddy. If the saved spot is off-screen (e.g.
        the user unplugged a second monitor since last run) we fall back
        to the default placement instead of orphaning the window."""
        key_x = f"win_x_{self.buddy.bag_id}"
        key_y = f"win_y_{self.buddy.bag_id}"
        x = self.store.get_meta(key_x)
        y = self.store.get_meta(key_y)
        if x is not None and y is not None:
            try:
                ix, iy = int(x), int(y)
            except ValueError:
                ix = iy = None
            if ix is not None and self._point_on_screen(ix, iy):
                self.window.move(ix, iy)
                return
        # Default placement: bottom-right + slot offset to the left so
        # slot 0 is rightmost, slot 1 sits 110px left of it, slot 2 220px.
        offset = 24 + self.slot_index * 110
        self.window.move_to_bottom_right(margin=offset)

    @staticmethod
    def _point_on_screen(x: int, y: int) -> bool:
        """Return True iff the given top-left coord falls inside any
        connected screen's available geometry (with a 4px slack so a
        point right on the edge still counts)."""
        from PySide6.QtGui import QGuiApplication
        for screen in QGuiApplication.screens():
            geo = screen.availableGeometry()
            if (geo.left() - 4 <= x <= geo.right() - 4
                    and geo.top() - 4 <= y <= geo.bottom() - 4):
                return True
        return False

    def save_position(self) -> None:
        pos = self.window.pos()
        self.store.set_meta(f"win_x_{self.buddy.bag_id}", str(pos.x()))
        self.store.set_meta(f"win_y_{self.buddy.bag_id}", str(pos.y()))

    def cleanup(self) -> None:
        """Tear down — used when leaving the party or quitting the app."""
        try:
            self.save_position()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.chatter.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.window.close()
            self.window.deleteLater()
        except Exception:  # noqa: BLE001
            pass

    def _refresh_sprite(self) -> None:
        """Push the current (sprite_style, buddy) combo into the PetWindow
        AND re-apply the per-dex display-scale override. Single source of
        truth for sprite plumbing so style switches / evolutions / reloads
        all keep the scale in sync."""
        from . import display_scale
        self.window.set_sprite_path(
            get_buddy_sprite_with_fallback(
                self.sprite_style, self.buddy.dex_id, self.buddy.is_rare,
            )
        )
        # Resizes the window too so high scales (up to 3×) aren't clipped.
        self.window.set_display_scale(display_scale.get(self.buddy.dex_id))

    # ---- public API used by BuddyApp ----
    def reload_buddy(self) -> None:
        """Refresh `self.buddy` from the DB (after evolution, rename, etc.)
        and update the sprite to match."""
        fresh = self.store.get_bag_entry(self.buddy.bag_id)
        if fresh is None:
            return
        self.buddy = fresh
        self._refresh_sprite()
        self._update_status()

    def set_sprite_style(self, style: str) -> None:
        self.sprite_style = style
        self._refresh_sprite()

    def update_status(self) -> None:
        self._update_status()

    # ---- actions (called by BuddyApp on behalf of popup / left-click) ----
    def on_pet(self) -> None:
        self.store.bump_friendship(self.buddy, FRIENDSHIP_PET)
        self.buddy = self.store.get_bag_entry(self.buddy.bag_id) or self.buddy
        line = messages.pick(messages.PET, self.buddy.friendship)
        self.window.say(line, 1800)
        self.anim.play("happy")
        self._update_status()

    def on_feed(self) -> None:
        # Eat a RANDOM food so it's a different one each time.
        food_key = self.store.random_available_of_kind(ItemKind.FOOD.value)
        if food_key is None or not self.store.consume_item(food_key, 1):
            self.window.say("먹을 게 없네… 🍎 모아야 해!", 2400)
            return
        item = find_item(food_key)
        leveled = self.store.gain_exp(self.buddy, FEED_EXP)
        self.store.bump_friendship(
            self.buddy,
            FRIENDSHIP_FEED + (FRIENDSHIP_LEVEL_UP if leveled else 0),
        )
        self.buddy = self.store.get_bag_entry(self.buddy.bag_id) or self.buddy
        if leveled:
            self._after_level_up()
        else:
            emoji = item.emoji if item else "🍎"
            self.window.say(f"{emoji} {messages.pick_food_line(food_key)}", 2400)
            self.anim.play("eat")
        self._update_status()

    def on_play(self) -> None:
        # Play with a RANDOM toy so it varies each time.
        toy_key = self.store.random_available_of_kind(ItemKind.TOY.value)
        if toy_key is None or not self.store.consume_item(toy_key, 1):
            self.window.say("장난감이 없어… 🎾 찾아봐!", 2400)
            return
        item = find_item(toy_key)
        leveled = self.store.gain_exp(self.buddy, PLAY_EXP)
        self.store.bump_friendship(
            self.buddy,
            FRIENDSHIP_PLAY + (FRIENDSHIP_LEVEL_UP if leveled else 0),
        )
        self.buddy = self.store.get_bag_entry(self.buddy.bag_id) or self.buddy
        if leveled:
            self._after_level_up()
        else:
            emoji = item.emoji if item else "🎾"
            self.window.say(f"{emoji} {messages.pick_toy_line(toy_key)}", 2400)
            self.anim.play("happy")
        self._update_status()

    def on_train(self) -> None:
        leveled = self.store.gain_exp(self.buddy, TRAIN_EXP)
        self.store.bump_friendship(
            self.buddy,
            FRIENDSHIP_TRAIN + (FRIENDSHIP_LEVEL_UP if leveled else 0),
        )
        self.buddy = self.store.get_bag_entry(self.buddy.bag_id) or self.buddy
        if leveled:
            self._after_level_up()
        else:
            line = messages.pick(messages.TRAIN, self.buddy.friendship)
            self.window.say(line, 2400)
            self.anim.play("train")
        self._update_status()

    def apply_passive_gain(self) -> None:
        """Tick handler — called every BuddyApp tick. Drips a tiny amount
        of EXP + friendship XP every PASSIVE_INTERVAL_S of unlocked time."""
        now = time.time()
        if now - self._last_passive_at < PASSIVE_INTERVAL_S:
            return
        self._last_passive_at = now
        leveled = self.store.gain_exp(self.buddy, PASSIVE_EXP)
        self.store.bump_friendship(self.buddy, PASSIVE_FRIENDSHIP_XP)
        self.buddy = self.store.get_bag_entry(self.buddy.bag_id) or self.buddy
        if leveled:
            self._after_level_up()
        self._update_status()

    # ---- internal ----
    def _after_level_up(self) -> None:
        """Speech + animation + emit so BuddyApp can offer evolution."""
        self.window.say(f"레벨업! Lv.{self.buddy.level} 🎉", 2500)
        self.anim.play("surprised")
        self.anim.play_halo()
        self.leveled_up.emit(self)

    def _on_chatter(self, text: str) -> None:
        self.window.say(text, 3500)

    def _on_daily_greeting(self, exp_gained: int) -> None:
        # Reload to reflect the chatter engine's EXP + friendship bumps.
        self.reload_buddy()
        self.anim.play("happy")

    def _update_status(self) -> None:
        b = self.buddy
        hearts = "❤️" * b.hearts + "♡" * (5 - b.hearts)
        text = (
            f"{b.display_name}  Lv.{b.level}  {hearts}\n"
            f"EXP {b.exp}/{b.exp_to_next}  ·  친밀도 {b.friendship}/100"
        )
        self.window.set_status_text(text)
