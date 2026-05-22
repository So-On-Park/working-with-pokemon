"""Wall-clock scheduled greetings (출근 / 점심 / 퇴근).

Distinct from the interval-based `ReminderScheduler` — those measure
elapsed minutes since last fire. This one watches the wall clock and
fires each event once per local workday, the first time the user is
online past the configured hour. If the PC was off when 12:00 came and
went, the event simply doesn't fire that day (no retroactive 'you missed
lunch' notifications).

Event times live in the `daily_events` table (user-editable from the
일정 tab). Three fixed events: morning / lunch / farewell. Each draws
its line from a personality-flavored bank in `messages.py`, so the same
18:00 퇴근 alarm sounds different on a 장난꾸러기 vs. a 차분한 buddy."""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Callable, Dict

from PySide6.QtCore import QObject, QTimer, Signal

from .config import SCHEDULE_CHECK_MS, WORK_DAYS
from . import messages
from .state import Buddy, Store
from .windows_state import is_screen_locked

log = logging.getLogger(__name__)


# Each event key maps to the picker that returns a personality-flavored
# line for that slot. The three keys are fixed (matching the DB seed).
_PICKERS: Dict[str, Callable[[messages.Personality], str]] = {
    "morning":  messages.pick_morning,
    "lunch":    messages.pick_lunch,
    "farewell": messages.pick_farewell,
}


class DailyScheduleEngine(QObject):
    """Emits `fired(text)` when a scheduled event triggers. Read the times
    from the DB every tick so edits made in the 일정 tab take effect
    immediately (no need to restart)."""

    fired = Signal(str)

    def __init__(self, store: Store, get_buddy,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self._get_buddy = get_buddy
        self._timer = QTimer(self)
        self._timer.setInterval(SCHEDULE_CHECK_MS)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._timer.start()
        # Initial sweep shortly after startup so a morning greeting fires
        # immediately if the user opened the app right after work_start.
        QTimer.singleShot(3000, self._tick)

    def stop(self) -> None:
        self._timer.stop()

    def check_now(self) -> None:
        """External hook — called by the app after a save in the schedule
        edit panel, so a freshly-enabled / re-timed event can fire on the
        next tick (or right away if it's already due)."""
        self._tick()

    def _tick(self) -> None:
        # Locked workstation → don't fire AND don't mark `last_fired` for
        # today. If the user is locked at 12:00 and unlocks at 12:30, we
        # want lunch to fire at 12:30, not be silently consumed.
        if is_screen_locked():
            return
        now = _dt.datetime.now()
        if now.weekday() not in WORK_DAYS:
            return
        buddy: Buddy | None = self._get_buddy()
        if buddy is None:
            return
        today_iso = now.date().isoformat()
        for event in self.store.list_schedule_events():
            if not event.enabled:
                continue
            target = now.replace(hour=event.hour, minute=event.minute,
                                 second=0, microsecond=0)
            if now < target:
                continue
            meta_key = f"daily_{event.key}_last_fired"
            if self.store.get_meta(meta_key) == today_iso:
                continue

            line = self._line_for(event, buddy)
            if not line:
                # No message resolvable — skip without consuming today's
                # fire slot so the user can fix the alarm and try again.
                continue
            # Mark fired only after we successfully resolved a line.
            self.store.set_meta(meta_key, today_iso)
            self.fired.emit(line)

    def _line_for(self, event, buddy) -> str:
        """Resolve the actual text to say. Custom alarms with an explicit
        message use it verbatim; built-ins fall through to their
        personality-flavored picker."""
        if event.message:
            return event.message
        if event.is_builtin:
            picker = _PICKERS.get(event.key)
            if picker is None:
                return ""
            try:
                personality = messages.personality_for(buddy.personality)
                return picker(personality)
            except Exception as exc:  # noqa: BLE001
                log.debug("schedule pick %s failed: %s", event.key, exc)
                return ""
        return ""
