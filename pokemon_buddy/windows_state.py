"""Tiny platform-state helper.

Right now it just exposes `is_screen_locked()` — used by the background
engines (encounter / item drop / reminder / schedule / passive gains) to
skip their work while the user can't see the buddy. Locked screen = the
buddy and its bubble are hidden behind the lock UI, so any activity
they'd surface is wasted at best, annoying at worst (the scheduled
12:00 lunch alarm marking itself "fired today" while the user is in a
meeting and unlocks at 13:30, for instance).

On non-Windows platforms the function returns False (treat as 'user
present') so the engines run as before."""

from __future__ import annotations

import logging
import sys

log = logging.getLogger(__name__)


def is_screen_locked() -> bool:
    """Return True when the Windows workstation is locked.

    Uses `OpenInputDesktop` + `GetUserObjectInformation` — when the
    workstation is locked, the input desktop switches from "Default" to
    "Winlogon" (or "Secure Desktop"), and that name change is what we
    detect. The call is cheap (microseconds) so it's safe to invoke from
    per-minute tick loops."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        user32 = ctypes.windll.User32
        DESKTOP_READOBJECTS = 0x0001
        UOI_NAME = 2
        hdesk = user32.OpenInputDesktop(0, False, DESKTOP_READOBJECTS)
        if not hdesk:
            # Couldn't even open the input desktop — almost certainly
            # because it's the secure desktop.
            return True
        try:
            size = ctypes.c_ulong(0)
            user32.GetUserObjectInformationW(
                hdesk, UOI_NAME, None, 0, ctypes.byref(size),
            )
            buf = ctypes.create_unicode_buffer(size.value)
            user32.GetUserObjectInformationW(
                hdesk, UOI_NAME, buf, size.value, ctypes.byref(size),
            )
            return buf.value.lower() != "default"
        finally:
            user32.CloseDesktop(hdesk)
    except Exception as exc:  # noqa: BLE001
        # Detection failure shouldn't break the app — fall back to
        # "user present" so background engines keep running.
        log.debug("is_screen_locked check failed: %s", exc)
        return False
