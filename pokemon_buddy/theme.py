"""색상 테마 — the app's point colour, picked from a starter's palette.

Every accent in the UI (buttons, the active nav tab, the level pill, the
EXP gauge, headlines) used to be the literal `#4a7ddc`, repeated across
eleven files. They all read from here now, so a theme swap is one setting
instead of a find-and-replace.

Each palette is the starter's colour with ~30% white mixed in — the look
of the vivid hue at partial opacity. That keeps the surfaces BRIGHT
(value 78-96%) while pulling saturation down to 35-67%, so the chrome
reads as soft rather than either loud or muddy. Darkening instead of
lightening was the wrong lever: it made everything dingy.

Bright surfaces can't carry white text, so every theme pairs its primary
with a deep same-hue `on_primary` instead of assuming white. All four
clear 4.5:1 — `test_yellow_theme_uses_dark_text` enforces it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class Theme:
    key: str
    label: str
    primary: str        # buttons, active tab, gauges, headlines
    primary_dark: str   # hover / border — a shade down from primary
    primary_light: str  # secondary chips (non-primary party slots)
    on_primary: str     # text drawn ON primary; NOT always white
    tint: str           # card background for the 대표 buddy
    tint_soft: str      # card background for the other party members
    rgb: Tuple[int, int, int]   # primary as ints, for rgba() stylesheets


THEMES: Dict[str, Theme] = {
    "squirtle": Theme(
        key="squirtle", label="💧 꼬부기",
        primary="#77b1df", primary_dark="#549cd7",
        primary_light="#b5d4ee", on_primary="#102536",
        tint="#ecf4fa", tint_soft="#f5f9fd", rgb=(119, 177, 223),
    ),
    "charmander": Theme(
        key="charmander", label="🔥 파이리",
        primary="#eb876d", primary_dark="#e56948",
        primary_light="#f4beb0", on_primary="#3b160c",
        tint="#fceeea", tint_soft="#fef6f5", rgb=(235, 135, 109),
    ),
    "bulbasaur": Theme(
        key="bulbasaur", label="🌿 이상해씨",
        primary="#82c795", primary_dark="#61b97a",
        primary_light="#bbe1c6", on_primary="#142e1b",
        tint="#edf7f0", tint_soft="#f6fbf7", rgb=(130, 199, 149),
    ),
    "pikachu": Theme(
        key="pikachu", label="⚡ 피카츄",
        primary="#f6cd50", primary_dark="#f4c023",
        primary_light="#fae4a0", on_primary="#3f3001",
        tint="#fef8e6", tint_soft="#fefbf2", rgb=(246, 205, 80),
    ),
}

# Display order for the tray menu.
THEME_ORDER: List[str] = ["squirtle", "charmander", "bulbasaur", "pikachu"]

# 꼬부기 is the closest match to the original blue, so existing installs
# keep the look they already had until the user picks something else.
DEFAULT_THEME = "squirtle"

_current: Theme = THEMES[DEFAULT_THEME]


def choices() -> List[Tuple[str, str]]:
    """(key, label) pairs in menu order."""
    return [(k, THEMES[k].label) for k in THEME_ORDER]


def normalize(key: str | None) -> str:
    return key if key in THEMES else DEFAULT_THEME


def set_current(key: str | None) -> Theme:
    global _current
    _current = THEMES[normalize(key)]
    return _current


def current() -> Theme:
    return _current


# Shorthand accessors — these read better inside f-string stylesheets than
# `theme.current().primary` repeated everywhere.
def primary() -> str:
    return _current.primary


def primary_dark() -> str:
    return _current.primary_dark


def primary_light() -> str:
    return _current.primary_light


def on_primary() -> str:
    return _current.on_primary


def tint() -> str:
    return _current.tint


def tint_soft() -> str:
    return _current.tint_soft


def primary_rgba(alpha: int) -> str:
    """`rgba(r, g, b, a)` for Qt stylesheets that need a translucent wash
    (Qt takes 0-255 alpha here, not the CSS 0-1 float)."""
    r, g, b = _current.rgb
    return f"rgba({r}, {g}, {b}, {alpha})"
