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

import ctypes
import logging
import sys
from ctypes import wintypes

log = logging.getLogger(__name__)


# ---- WTS session state (primary signal) ----------------------------------
# WTSQuerySessionInformationW(WTSSessionInfoEx) reports the lock state the
# session manager itself tracks, which is the same thing that drives the
# WM_WTSSESSION_CHANGE lock/unlock events.

_WTS_CURRENT_SERVER_HANDLE = 0
_WTS_CURRENT_SESSION = 0xFFFFFFFF   # (DWORD)-1
_WTS_SESSION_INFO_EX = 25
_WTS_SESSIONSTATE_LOCK = 0
_WTS_SESSIONSTATE_UNLOCK = 1


class _WTSINFOEX_LEVEL1_W(ctypes.Structure):
    _fields_ = [
        ("SessionId", wintypes.ULONG),
        ("SessionState", ctypes.c_int),
        ("SessionFlags", ctypes.c_long),
        ("WinStationName", wintypes.WCHAR * 33),
        ("UserName", wintypes.WCHAR * 21),
        ("DomainName", wintypes.WCHAR * 18),
        ("LogonTime", wintypes.LARGE_INTEGER),
        ("ConnectTime", wintypes.LARGE_INTEGER),
        ("DisconnectTime", wintypes.LARGE_INTEGER),
        ("LastInputTime", wintypes.LARGE_INTEGER),
        ("CurrentTime", wintypes.LARGE_INTEGER),
        ("IncomingBytes", wintypes.DWORD),
        ("OutgoingBytes", wintypes.DWORD),
        ("IncomingFrames", wintypes.DWORD),
        ("OutgoingFrames", wintypes.DWORD),
        ("IncomingCompressedBytes", wintypes.DWORD),
        ("OutgoingCompressedBytes", wintypes.DWORD),
    ]


class _WTSINFOEX(ctypes.Structure):
    _fields_ = [("Level", wintypes.DWORD), ("Data", _WTSINFOEX_LEVEL1_W)]


def _wts_locked() -> bool | None:
    """True/False from the session manager, or None if unavailable."""
    try:
        wts = ctypes.windll.Wtsapi32
        wts.WTSQuerySessionInformationW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, ctypes.c_int,
            ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.DWORD),
        ]
        wts.WTSQuerySessionInformationW.restype = wintypes.BOOL
        wts.WTSFreeMemory.argtypes = [ctypes.c_void_p]

        buf = ctypes.c_void_p()
        nbytes = wintypes.DWORD(0)
        ok = wts.WTSQuerySessionInformationW(
            _WTS_CURRENT_SERVER_HANDLE, _WTS_CURRENT_SESSION,
            _WTS_SESSION_INFO_EX, ctypes.byref(buf), ctypes.byref(nbytes),
        )
        if not ok or not buf:
            return None
        try:
            info = ctypes.cast(buf, ctypes.POINTER(_WTSINFOEX)).contents
            if info.Level != 1:
                return None
            flags = info.Data.SessionFlags
            if flags == _WTS_SESSIONSTATE_LOCK:
                return True
            if flags == _WTS_SESSIONSTATE_UNLOCK:
                return False
            return None
        finally:
            wts.WTSFreeMemory(buf)
    except Exception as exc:  # noqa: BLE001
        log.debug("WTS lock probe failed: %s", exc)
        return None


# ---- input desktop name (fallback) ---------------------------------------

def _input_desktop_locked() -> bool:
    """Legacy probe: the input desktop switches away from "Default" once
    the secure desktop takes over. Kept as a fallback because it only
    catches the credential-prompt stage — on Windows 11 the lock screen
    itself still runs on "Default", which is exactly why this alone let
    the buddy keep levelling all night."""
    try:
        user32 = ctypes.windll.User32
        DESKTOP_READOBJECTS = 0x0001
        UOI_NAME = 2
        # HDESK is pointer-sized; without an explicit restype ctypes
        # truncates it to a 32-bit int and the follow-up calls get a
        # bogus handle.
        user32.OpenInputDesktop.restype = ctypes.c_void_p
        user32.OpenInputDesktop.argtypes = [
            wintypes.DWORD, wintypes.BOOL, wintypes.DWORD,
        ]
        user32.CloseDesktop.argtypes = [ctypes.c_void_p]
        user32.GetUserObjectInformationW.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
            wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
        ]

        hdesk = user32.OpenInputDesktop(0, False, DESKTOP_READOBJECTS)
        if not hdesk:
            # Couldn't even open the input desktop — almost certainly
            # because it's the secure desktop.
            return True
        try:
            size = wintypes.DWORD(0)
            user32.GetUserObjectInformationW(
                hdesk, UOI_NAME, None, 0, ctypes.byref(size),
            )
            if not size.value:
                return False
            buf = ctypes.create_unicode_buffer(size.value)
            if not user32.GetUserObjectInformationW(
                hdesk, UOI_NAME, buf, size.value, ctypes.byref(size),
            ):
                return False
            return buf.value.lower() != "default"
        finally:
            user32.CloseDesktop(hdesk)
    except Exception as exc:  # noqa: BLE001
        log.debug("input-desktop lock probe failed: %s", exc)
        return False


def is_screen_locked() -> bool:
    """Return True when the Windows workstation is locked.

    Asks the session manager first (authoritative, and the only one of the
    two that sees the Windows 11 lock screen), then falls back to the
    input-desktop name. The calls are cheap so this is safe to invoke from
    per-tick loops."""
    if sys.platform != "win32":
        return False
    state = _wts_locked()
    if state is not None:
        return state
    return _input_desktop_locked()
