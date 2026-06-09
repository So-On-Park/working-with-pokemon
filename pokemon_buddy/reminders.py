"""Reminder scheduler. Polls the reminders table once per minute on the GUI
thread and emits `fired` for any reminder whose interval has elapsed."""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, QTimer, Signal

from .state import Reminder, Store
from .windows_state import is_screen_locked


class ReminderScheduler(QObject):
    """Emits `fired(Reminder)` whenever a due reminder should be delivered.

    A small per-reminder grace prevents rapid double-firing after the user
    edits a reminder: we update `last_fired_at` immediately on fire."""

    fired = Signal(object)  # Reminder

    CHECK_INTERVAL_MS = 60_000  # 60s — fine-grained enough for minute-level scheduling
    # Stagger multiple due reminders so the buddy doesn't talk over itself
    STAGGER_MS = 2500

    def __init__(self, store: Store, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._pending: list[Reminder] = []
        self._dispatch_timer = QTimer(self)
        self._dispatch_timer.setSingleShot(True)
        self._dispatch_timer.timeout.connect(self._dispatch_next)

    # ---- lifecycle ----
    def start(self) -> None:
        # Rebaseline every reminder's clock to "now" on launch. Interval
        # reminders are recurring timers, not a backlog: if the PC was off
        # all night, the user doesn't want every reminder dumped at once the
        # moment they open the app (출근 직후 한꺼번에 발사되던 버그). Starting
        # the app starts the timers fresh — each fires one interval later.
        now = time.time()
        for r in self.store.list_reminders():
            self.store.mark_reminder_fired(r.id, now)
        self._timer.start(self.CHECK_INTERVAL_MS)

    def stop(self) -> None:
        self._timer.stop()
        self._dispatch_timer.stop()
        self._pending.clear()

    # Force an immediate check (used for testing or after edits)
    def check_now(self) -> None:
        self._tick()

    # ---- internals ----
    def _tick(self) -> None:
        # Skip firing while the workstation is locked. We don't mark
        # `last_fired_at` either — once the user unlocks, the reminder is
        # immediately due again and the next tick delivers it.
        if is_screen_locked():
            return
        now = time.time()
        due = [r for r in self.store.list_reminders() if r.is_due(now)]
        if not due:
            return
        # Mark every due reminder fired right away to avoid duplicates if the
        # next tick lands before the user dismisses the toast.
        for r in due:
            self.store.mark_reminder_fired(r.id, now)
            r.last_fired_at = now
        # Queue and stagger their emission.
        self._pending.extend(due)
        if not self._dispatch_timer.isActive():
            self._dispatch_next()

    def _dispatch_next(self) -> None:
        if not self._pending:
            return
        r = self._pending.pop(0)
        self.fired.emit(r)
        if self._pending:
            self._dispatch_timer.start(self.STAGGER_MS)
