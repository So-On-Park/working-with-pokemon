"""Ambient chatter — the buddy says spontaneous lines through the day,
themed by the current friendship tier (awkward / budding / friendly /
affectionate). Also handles the once-a-day greeting + EXP bonus.

All line banks live in `messages.py`. This module just times when to fire
and which bank to draw from."""

from __future__ import annotations

import logging
import random
import time
from datetime import date

from PySide6.QtCore import QObject, QTimer, Signal

from .config import (
    CHATTER_CHECK_MS,
    DAILY_GREETING_EXP_BONUS,
    FRIENDSHIP_DAILY_GREETING,
)
from . import messages
from .state import Store

log = logging.getLogger(__name__)


class ChatterEngine(QObject):
    """Emits `chatter(text)` for the app to surface via the speech bubble.
    Daily greeting EXP + friendship are applied inside the engine."""

    chatter = Signal(str)
    daily_greeting = Signal(int)  # exp gained (app refreshes status)

    def __init__(self, store: Store, get_buddy,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.store = store
        # get_buddy returns the current Buddy — so swaps are auto-tracked.
        self._get_buddy = get_buddy

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        # First ambient line picked using the current friendship tier.
        self._last_chat_at = time.time()
        self._next_delay = self._compute_next_delay()

    def _compute_next_delay(self) -> int:
        b = self._get_buddy()
        if b is None:
            return 5 * 60
        return messages.next_chatter_interval(b.friendship)

    def start(self) -> None:
        # Daily greeting fires shortly after startup if it's a new local day.
        QTimer.singleShot(2500, self._maybe_daily_greeting)
        self._timer.start(CHATTER_CHECK_MS)

    def stop(self) -> None:
        self._timer.stop()

    # ---- greeting ----
    def _maybe_daily_greeting(self) -> None:
        """Once-per-local-day startup line. If the user has been absent for
        24h+ (PC off, weekend, vacation, etc.) a personality-flavored
        welcome-back line replaces the standard daily greeting. Either way
        the buddy gets the same EXP / friendship bonus."""
        today = date.today().isoformat()
        last = self.store.get_meta("last_greeting_date")
        if last == today:
            return
        self.store.set_meta("last_greeting_date", today)

        buddy = self._get_buddy()
        if buddy is None:
            return
        self.store.gain_exp(buddy, DAILY_GREETING_EXP_BONUS)
        self.store.bump_friendship(buddy, FRIENDSHIP_DAILY_GREETING)

        personality = messages.personality_for(buddy.personality)
        absence_hours = max(
            0.0, (time.time() - buddy.last_interaction_at) / 3600.0,
        )
        welcome = messages.pick_welcome_back(personality, absence_hours)
        if welcome is not None:
            line = f"{welcome}  (+{DAILY_GREETING_EXP_BONUS} EXP)"
        else:
            base = messages.pick(messages.GREETING, buddy.friendship)
            line = f"{base}  (+{DAILY_GREETING_EXP_BONUS} EXP)"
        self.chatter.emit(line)
        self.daily_greeting.emit(DAILY_GREETING_EXP_BONUS)

    # ---- ambient ----
    def _tick(self) -> None:
        now = time.time()
        if now - self._last_chat_at < self._next_delay:
            return
        buddy = self._get_buddy()
        if buddy is not None:
            personality = messages.personality_for(buddy.personality)
            line = messages.pick_chatter(personality, buddy.friendship)
            if line:
                self.chatter.emit(line)
        self._last_chat_at = now
        self._next_delay = self._compute_next_delay()
