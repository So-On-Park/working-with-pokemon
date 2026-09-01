from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "PokemonBuddy"


def _user_base_dir() -> Path:
    """Per-user, always-writable data root. Used by the FROZEN app so it
    works no matter where it was installed — Program Files (read-only for
    standard users), a per-user Programs dir, or a portable folder all share
    one writable home under %LOCALAPPDATA%."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APP_DIR_NAME


# Two anchors:
#   INSTALL_DIR — where the program files live (next to the .exe when frozen;
#                 the repo root in dev). Read-only under a Program Files
#                 install. Holds the shipped seed assets (icon, custom seed).
#   ROOT/BASE   — the writable home for all user state. Frozen → per-user
#                 %LOCALAPPDATA%\PokemonBuddy; dev → the repo root so tests
#                 and local runs keep using ./data and ./assets unchanged.
if getattr(sys, "frozen", False):
    INSTALL_DIR = Path(sys.executable).resolve().parent
    ROOT = _user_base_dir()
else:
    INSTALL_DIR = Path(__file__).resolve().parent.parent
    ROOT = INSTALL_DIR

# Shipped, read-only seed assets that ride along with the install (custom
# pokemon the distributor bundled, etc.). In dev this equals ASSETS_DIR.
BUNDLED_ASSETS_DIR = INSTALL_DIR / "assets"

ASSETS_DIR = ROOT / "assets"
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "buddy.db"
# User-authored sprite cache (custom pokemon GIFs). Lives under data/ — the
# only truly irreplaceable sprite art — so a distribution update that
# overwrites assets/ (bundled + re-downloadable vanilla sprites) never wipes
# the user's own creations. See migrate_user_data().
CUSTOM_SPRITES_DIR = DATA_DIR / "custom_sprites"

ASSETS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
CUSTOM_SPRITES_DIR.mkdir(parents=True, exist_ok=True)


def _copy_if_absent(src: Path, dest: Path) -> None:
    """Copy src→dest only when dest doesn't exist yet. Non-destructive and
    idempotent; swallows IO errors so a locked/odd file never blocks boot."""
    import shutil
    try:
        if src.is_file() and not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
    except OSError:
        pass


def _relocate_irreplaceable_from(src_base: Path) -> None:
    """Copy the irreplaceable user files out of a legacy layout rooted at
    `src_base` (which has its own data/ + assets/) into the current writable
    ROOT. Only the files that can't be re-downloaded are pulled — vanilla
    PokeAPI sprite gifs are skipped (they re-fetch on demand)."""
    src_data = src_base / "data"
    src_assets = src_base / "assets"

    # SQLite DB + JSON registries (old installs kept these under data/ or,
    # even older, under assets/).
    _copy_if_absent(src_data / "buddy.db", DB_PATH)
    for fname in ("custom_pokemon.json", "display_scale.json"):
        _copy_if_absent(src_data / fname, DATA_DIR / fname)
        _copy_if_absent(src_assets / fname, DATA_DIR / fname)
    # Offline name/info caches — nice to keep so names don't blank out offline.
    for fname in ("names_ko.json", "names_eng.json", "names_info.json",
                  "species_info.json"):
        _copy_if_absent(src_assets / fname, ASSETS_DIR / fname)
    # Custom pokemon sprites: from a modern data/custom_sprites/ or the older
    # flat assets/ layout (dex_id >= 9001).
    try:
        legacy_custom = src_data / "custom_sprites"
        if legacy_custom.is_dir():
            for gif in legacy_custom.glob("*.gif"):
                _copy_if_absent(gif, CUSTOM_SPRITES_DIR / gif.name)
        if src_assets.is_dir():
            for gif in src_assets.glob("*.gif"):
                num = gif.stem.split("_", 1)[0]
                if num.isdigit() and int(num) >= 9001:
                    _copy_if_absent(gif, CUSTOM_SPRITES_DIR / gif.name)
    except OSError:
        pass


def migrate_user_data() -> None:
    """Make sure the writable ROOT holds the player's progress, no matter
    which layout the previous version used. All copies are non-destructive
    (skip when the destination already exists), so this is safe to call once
    every launch.

    Covers:
      • Frozen installs: pull state out of the old exe-adjacent layout
        (portable zip builds wrote data/ next to the .exe) and seed any
        custom pokemon the distribution bundled under the install dir.
      • Every mode: relocate user-authored files that older builds kept in
        assets/ into data/ (the update-safe dir)."""
    # 1) Frozen: legacy exe-adjacent data + bundled seed → %LOCALAPPDATA%.
    if getattr(sys, "frozen", False):
        if INSTALL_DIR.resolve() != ROOT.resolve():
            _relocate_irreplaceable_from(INSTALL_DIR)

    # 2) Any mode: assets/ → data/ relocation within ROOT (custom registry +
    #    display scale + custom sprites authored by pre-data/ builds).
    for fname in ("custom_pokemon.json", "display_scale.json"):
        _copy_if_absent(ASSETS_DIR / fname, DATA_DIR / fname)
    try:
        for gif in ASSETS_DIR.glob("*.gif"):
            num = gif.stem.split("_", 1)[0]  # "9001_bw" -> "9001"
            if num.isdigit() and int(num) >= 9001:
                _copy_if_absent(gif, CUSTOM_SPRITES_DIR / gif.name)
    except OSError:
        pass

# Buddy display
BUDDY_BOX_PX = 88
SPEECH_BUBBLE_PX = 26
TARGET_DISPLAY_PX = 64

APP_NAME = "Pokemon Buddy"
# Windows AppUserModelID — also serves as the display name on toast
# notifications when no shortcut DisplayName is registered. Kept short
# and friendly so alarms read as "포켓버디" instead of a developer-y
# "SoOnPark.PokemonBuddy" string.
APP_ID = "포켓버디"

# Shared dialog width — one MainPanel window hosts all four tabs
# (bag / inventory / dex / reminders) via a QStackedWidget. This is the
# fixed size of that window.
# Main window (내 포켓몬 / 내 가방 / 도감 / 리마인더 탭 host). Widened from
# 400 so the 4-column 도감 grid has room for its scrollbar — the right-hand
# column used to be clipped.
DIALOG_W = 440
DIALOG_H = 540

# Action animations
ANIM_TICK_MS = 16
HAPPY_MAX_SCALE = 1.20
EAT_MAX_ROT_DEG = 10.0
TRAIN_NOD_DEG = 6.0
SURPRISED_MAX_SCALE = 1.25
SAD_TILT_DEG = -8.0

# Sprite styles for the buddy. Only two user-facing modes now — different
# appearance (shiny) is folded into the rare-Pokemon system instead.
# `bw`       = PokeAPI Gen 5 Black/White animated (small pixel art)
# `showdown` = Pokemon Showdown's animated battle sprites (larger, smoother)
SPRITE_STYLES = [
    ("bw",       "도트 (Gen 5)"),
    ("showdown", "쇼다운 애니메이션"),
]
DEFAULT_SPRITE_STYLE = "showdown"

# Bulk download — Gen 1 only for the encounter pool we already support.
BULK_DEX_RANGE = (1, 151)

# Friendship — 0..100. Awarded on actions; decays slowly on neglect.
# Sole relationship stat (hunger / happiness are gone).
#
# Internally there's a hidden `friendship_xp` accumulator per buddy. Each
# action grants XP; once it covers the current band's price (see
# `friendship_xp_for` below), the visible friendship integer goes up by 1.
# Calibrated so that simply KEEPING the buddy on screen caps friendship at
# 100 in ≈96 hrs of screen time (see the passive section below); active
# feed/play/train + the daily greeting stack on top to get there faster.
# Friendship never decreases — there is no decay (see
# Store.apply_friendship_decay, a no-op).
# 친밀도 하트 — the 5-slot gauge shown in the popup / bag card / detail /
# tray tooltip. Both are colour emoji so the filled and empty halves match
# in weight and width; the old pairing of ❤️ (emoji) with ♡ (a thin outline
# glyph from the text font) rendered as two different-looking symbols.
# Swap these two strings to restyle every heart in the app at once.
HEART_FULL = "❤️"
HEART_EMPTY = "🤍"

FRIENDSHIP_DEFAULT = 0
# Friendship — rising cost in three bands, like the games (Gen 3+ shrinks
# the gain as the value climbs). Cheap early so affection feels responsive,
# expensive at the top so the last stretch means something.
#   0–49   : 60 XP/point   (→ 50 in ~30h)
#   50–79  : 100 XP/point  (→ 80 in ~60h — the 1.5x EXP bonus threshold)
#   80–100 : 180 XP/point  (→ 100 in ~96h)
FRIENDSHIP_XP_TIER_LOW_MAX = 50
FRIENDSHIP_XP_TIER_MID_MAX = 80
FRIENDSHIP_XP_LOW = 60
FRIENDSHIP_XP_MID = 100
FRIENDSHIP_XP_HIGH = 180


def friendship_xp_for(points: int) -> int:
    """XP needed to go from `points` to `points + 1` 친밀도."""
    if points < FRIENDSHIP_XP_TIER_LOW_MAX:
        return FRIENDSHIP_XP_LOW
    if points < FRIENDSHIP_XP_TIER_MID_MAX:
        return FRIENDSHIP_XP_MID
    return FRIENDSHIP_XP_HIGH


FRIENDSHIP_FEED = 8            # XP — was 1 friendship
FRIENDSHIP_PLAY = 8
FRIENDSHIP_TRAIN = 8
FRIENDSHIP_PET = 4             # left-click pet
FRIENDSHIP_CATCH_WILD = 8
FRIENDSHIP_LEVEL_UP = 12
FRIENDSHIP_DAILY_GREETING = 15
FRIENDSHIP_BONUS_MID = 60   # >= 60: 1.2x EXP
FRIENDSHIP_BONUS_HIGH = 80  # >= 80: 1.5x EXP

# Friendship tier breakpoints (also defined in messages.py — keep in sync).
TIER_AWKWARD_MAX = 20         # < 20
TIER_BUDDING_MAX = 50         # 20–49
TIER_FRIENDLY_MAX = 80        # 50–79
# 80+ is AFFECTIONATE

# Ambient chatter
CHATTER_CHECK_MS = 60_000
CHATTER_MIN_INTERVAL_S = 5 * 60
CHATTER_MAX_INTERVAL_S = 15 * 60
DAILY_GREETING_EXP_BONUS = 10

# Wall-clock greetings (출근 / 점심 / 퇴근). Each fires once per local day,
# only when the user actually opens the app past that time — they never
# show up retroactively if the PC was off, and they're skipped on
# weekends by default since the buddy lives on a work machine.
WORK_START_HOUR = 9      # 출근 인사
WORK_START_MINUTE = 0
LUNCH_HOUR = 12          # 점심 알람
LUNCH_MINUTE = 0
WORK_END_HOUR = 18       # 퇴근 인사
WORK_END_MINUTE = 0
# Weekdays only (0=Mon … 4=Fri). Set to [0,1,2,3,4,5,6] for daily greetings.
WORK_DAYS = [0, 1, 2, 3, 4]
SCHEDULE_CHECK_MS = 60_000  # poll the wall clock once a minute

# Welcome-back: the buddy reacts when the user shows up after a real
# absence (24h+). Decay is gone, but the dialogue still recognizes time.
ABSENCE_SHORT_HOURS = 24    # "오랜만이야"
ABSENCE_MEDIUM_HOURS = 72   # "며칠 만이네"
ABSENCE_LONG_HOURS = 168    # "한참 만이야!"

# Tick — periodic refresh of the status / passive gains.
TICK_MS = 30_000

# Level — rising curve: each level costs a bit more than the last, the way
# the games do it. Lv.1→2 is 55 EXP, Lv.99→100 is 545, and the whole climb
# is 29,700 EXP ≈ 148 hours of screen time (~3 weeks of workdays).
# Early levels land fast so a new buddy feels responsive; the last stretch
# is meant to be a commitment.
# MAX_LEVEL is the cap (the 명포수 skill auto-learns here).
MAX_LEVEL = 100
EXP_CURVE_BASE = 50
EXP_CURVE_STEP = 5


def exp_to_next_for(level: int) -> int:
    """EXP needed to get from `level` to `level + 1`."""
    return EXP_CURVE_BASE + EXP_CURVE_STEP * max(1, int(level))



# Passive XP + friendship gains while the buddy is open on the user's screen.
# This is the BACKBONE of progression: just keeping the buddy with you caps
# BOTH stats in ~100 hours of on-screen time — roughly two weeks of a normal
# workday. Active feed/play/train + the daily greeting stack on top to reach
# the cap sooner.
#   friendship: 25 XP × 4 ticks/hr = 100 XP/hr = +1 친밀도/hr  → ~100 hr to 100
#   level:      50 EXP × 4 ticks/hr = 200 EXP/hr = +1 레벨/hr   → ~100 hr to Lv.100
PASSIVE_INTERVAL_S = 15 * 60   # every 15 minutes of unlocked screen time
PASSIVE_EXP = 50
PASSIVE_FRIENDSHIP_XP = 25

# Action rewards — all stack on top of passive screen-time gains.
FEED_EXP = 10                  # feeding now grants EXP too (+친밀도 below)
PLAY_EXP = 15
TRAIN_EXP = 35
# 이상한사탕 grants no EXP at all — it raises the level by exactly 1, as in
# the games (Store.level_up_once). No constant to tune here.

# Default party placement — a level row along the bottom-right of the
# PRIMARY monitor. Reading order matches the party order: slot 0 (대표) is
# LEFTMOST, slot 2 hugs the right edge. Only used when a buddy has no
# saved position; dragging one anywhere overrides this for good.
PET_SCREEN_MARGIN = 24        # inset from the screen edges
PARTY_SLOT_GAP_PX = 18        # clear space between neighbouring buddies
# Fallback step for the rough per-agent placement (see BuddyApp's
# _layout_party_row for the exact, width-aware version).
PARTY_SLOT_STEP_PX = 110

# Starter dex entry — picked at first run.
STARTER_DEX_ID = 25

# Wild encounters
ENCOUNTER_CHECK_MS = 5 * 60 * 1000
ENCOUNTER_PROBABILITY = 0.30
ENCOUNTER_COOLDOWN_S = 10 * 60
ENCOUNTER_AUTO_FLEE_MS = 30_000
ENCOUNTER_DEX_RANGE = (1, 151)
CATCH_RATE = 0.75
CATCH_EXP_REWARD = 20
# Rare Pokemon — once a wild encounter is rolling, this is the chance the
# spawned Pokemon is the rare (shiny) variant. The dex tracks it as a
# separate entry. The species name is NEVER decorated: a shiny 피카츄 is
# still called 피카츄, exactly like in the games. It is marked visually
# with ✨ in the lists, and titled 이로치 in the detail dialog.
RARE_PROBABILITY = 0.01
# 이로치 — the Korean fan term for a shiny. Used as a title/badge, not as
# part of any name.
SHINY_LABEL = "이로치"

# Inventory — a single item key never stockpiles past this many. Enforced at
# the storage layer (Store.add_item clamps) AND in the bag UI display.
COUNT_CAP = 999

# Item drops — fruits / toys / pokeballs appear on screen for the user to
# collect into their bag (inventory). Items are completely static once
# placed (no bob, no sparkle) so they don't add peripheral-vision motion.
ITEM_DROP_CHECK_MS = 90_000          # poll every 90s
ITEM_DROP_PROBABILITY = 0.45         # chance per poll
ITEM_DROP_COOLDOWN_S = 75            # min seconds between drops
ITEM_DROP_AUTO_FADE_MS = 90_000      # disappear after 90s uncollected
ITEM_DROP_MAX_ACTIVE = 3             # how many can sit on screen at once
ITEM_DROP_SIZE_PX = 44               # window side (special/skill drops)
ITEM_DROP_SIZE_SMALL_PX = 32         # smaller side for food / toy / pokeball

# Skill scrolls — a rare "두루마리" (📜) drop. Rolled independently from the
# normal item drop so it stays a genuine surprise. Collecting one banks a
# skill teaching-scroll; using it teaches that skill to a chosen party member.
SKILL_DROP_PROBABILITY = 0.012       # per poll, on top of the normal roll
SKILL_DROP_AUTO_FADE_MS = 120_000    # scrolls linger a touch longer than items
# Magnetize: a party member that knows 수집광 (collector) pulls a fresh drop
# toward itself this long after it appears, then auto-collects it.
MAGNETIZE_DELAY_MS = 2000
MAGNETIZE_TRAVEL_MS = 650
