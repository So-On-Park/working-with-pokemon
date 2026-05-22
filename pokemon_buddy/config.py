from __future__ import annotations

import sys
from pathlib import Path

# PyInstaller frozen mode: __file__ points inside the temporary MEIPASS
# unpack dir, which gets wiped on app exit. Anything we write there
# (buddy.db, downloaded sprites, custom_pokemon.json) would vanish next
# run. Anchor user-writable directories next to the .exe instead.
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent.parent

ASSETS_DIR = ROOT / "assets"
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "buddy.db"

ASSETS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Buddy display
BUDDY_BOX_PX = 88
SPEECH_BUBBLE_PX = 26
TARGET_DISPLAY_PX = 64

APP_NAME = "Pokemon Buddy"
# Windows AppUserModelID — groups our windows / notifications under one
# taskbar entry. Format: <owner>.<app>, no spaces.
APP_ID = "SoOnPark.PokemonBuddy"

# Shared dialog width — one MainPanel window hosts all four tabs
# (bag / inventory / dex / reminders) via a QStackedWidget. This is the
# fixed size of that window.
DIALOG_W = 400
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
DEFAULT_SPRITE_STYLE = "bw"

# Bulk download — Gen 1 only for the encounter pool we already support.
BULK_DEX_RANGE = (1, 151)

# Friendship — 0..100. Awarded on actions; decays slowly on neglect.
# Sole relationship stat (hunger / happiness are gone).
#
# Internally there's a hidden `friendship_xp` accumulator per buddy. Each
# action grants XP; once `FRIENDSHIP_XP_PER_POINT` accumulates, the visible
# friendship integer goes up by 1. The values below are tuned so a moderate
# daily user (≈ 5 each of feed/play/train + 1 daily greeting) hits 100
# around the two-month mark; a heavy user gets there faster, a light user
# slower.
FRIENDSHIP_DEFAULT = 0
FRIENDSHIP_XP_PER_POINT = 100
FRIENDSHIP_FEED = 8            # XP — was 1 friendship
FRIENDSHIP_PLAY = 8
FRIENDSHIP_TRAIN = 8
FRIENDSHIP_PET = 4             # left-click pet
FRIENDSHIP_CATCH_WILD = 8
FRIENDSHIP_LEVEL_UP = 12
FRIENDSHIP_DAILY_GREETING = 15
FRIENDSHIP_DECAY_PER_DAY = 1
FRIENDSHIP_DECAY_AFTER_HOURS = 48
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

# Passive XP + friendship gains while the buddy is open on the user's
# screen. Small, slow, but visible — designed so spending a workday
# 'together' inches the values forward without dominating the active-
# action gain budget.
PASSIVE_INTERVAL_S = 15 * 60   # every 15 minutes of unlocked screen time
PASSIVE_EXP = 1                # +1 EXP toward the next level
PASSIVE_FRIENDSHIP_XP = 1      # +1 friendship XP (100 XP = +1 friendship)

# Action rewards. Feed gives only friendship; play/train give EXP + friendship.
PLAY_EXP = 15
TRAIN_EXP = 35

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
# spawned Pokemon is the rare (shiny) variant. Display name gets the
# "레어" prefix and the dex tracks it as a separate entry.
RARE_PROBABILITY = 0.01
RARE_NAME_PREFIX = "레어"

# Item drops — fruits / toys / pokeballs appear on screen for the user to
# collect into their bag (inventory). Items are completely static once
# placed (no bob, no sparkle) so they don't add peripheral-vision motion.
ITEM_DROP_CHECK_MS = 90_000          # poll every 90s
ITEM_DROP_PROBABILITY = 0.45         # chance per poll
ITEM_DROP_COOLDOWN_S = 75            # min seconds between drops
ITEM_DROP_AUTO_FADE_MS = 5 * 60_000  # disappear after 5 min uncollected
ITEM_DROP_MAX_ACTIVE = 3             # how many can sit on screen at once
ITEM_DROP_SIZE_PX = 44               # window side (emoji icon size)
