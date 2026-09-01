"""밸런스 곡선 — the numbers the pacing was chosen from.

Both curves were picked off a modelled table, so these tests pin the
totals rather than the formulas. If someone retunes base/step, the test
says exactly how much of the game's pacing moved."""

from __future__ import annotations

from pokemon_buddy.config import (
    FRIENDSHIP_XP_HIGH,
    FRIENDSHIP_XP_LOW,
    FRIENDSHIP_XP_MID,
    MAX_LEVEL,
    PASSIVE_EXP,
    PASSIVE_FRIENDSHIP_XP,
    PASSIVE_INTERVAL_S,
    exp_to_next_for,
    friendship_xp_for,
)

TICKS_PER_HOUR = 3600 / PASSIVE_INTERVAL_S      # 4
EXP_PER_HOUR = PASSIVE_EXP * TICKS_PER_HOUR      # 200
FS_XP_PER_HOUR = PASSIVE_FRIENDSHIP_XP * TICKS_PER_HOUR   # 100


# ---- level curve: 50 + 5×level ----

def test_level_curve_endpoints():
    assert exp_to_next_for(1) == 55
    assert exp_to_next_for(50) == 300
    assert exp_to_next_for(MAX_LEVEL - 1) == 545


def test_level_curve_is_strictly_rising():
    costs = [exp_to_next_for(lv) for lv in range(1, MAX_LEVEL)]
    assert costs == sorted(costs)
    assert costs[-1] > costs[0] * 9      # the climb genuinely steepens


def test_hours_to_max_level():
    total = sum(exp_to_next_for(lv) for lv in range(1, MAX_LEVEL))
    assert total == 29_700
    hours = total / EXP_PER_HOUR
    assert 145 <= hours <= 150, f"만렙까지 {hours:.0f}h — 목표 148h"


def test_early_levels_stay_quick():
    """Lv.10 inside a working day, or a new buddy feels dead."""
    to_ten = sum(exp_to_next_for(lv) for lv in range(1, 10))
    assert to_ten / EXP_PER_HOUR < 4.0


# ---- friendship curve: 60 / 100 / 180 ----

def test_friendship_bands():
    assert friendship_xp_for(0) == FRIENDSHIP_XP_LOW
    assert friendship_xp_for(49) == FRIENDSHIP_XP_LOW
    assert friendship_xp_for(50) == FRIENDSHIP_XP_MID
    assert friendship_xp_for(79) == FRIENDSHIP_XP_MID
    assert friendship_xp_for(80) == FRIENDSHIP_XP_HIGH
    assert friendship_xp_for(99) == FRIENDSHIP_XP_HIGH


def test_friendship_cost_never_falls():
    costs = [friendship_xp_for(p) for p in range(100)]
    assert costs == sorted(costs)


def test_hours_to_max_friendship():
    total = sum(friendship_xp_for(p) for p in range(100))
    assert total == 9_600
    hours = total / FS_XP_PER_HOUR
    assert 94 <= hours <= 98, f"친밀도 만렙까지 {hours:.0f}h — 목표 96h"


def test_exp_bonus_thresholds_arrive_earlier_than_before():
    """친밀도 60/80 are the 1.2x / 1.5x EXP gates. The whole point of the
    front-loaded curve is reaching them sooner than the old flat 100/point
    (which took 60h and 80h)."""
    to_60 = sum(friendship_xp_for(p) for p in range(60)) / FS_XP_PER_HOUR
    to_80 = sum(friendship_xp_for(p) for p in range(80)) / FS_XP_PER_HOUR
    assert to_60 < 60
    assert to_80 < 80


# ---- potions must still deliver exactly what they promise ----

def test_potion_grants_exact_points_across_a_band_boundary(store):
    """+10 친밀도 straddling the 50-point band used to under-deliver: the
    old code paid every point at the flat rate."""
    b = store.add_to_bag(1)
    b.friendship = 45
    b.friendship_xp = 0
    store.save_active_buddy(b)
    store.bump_friendship_points(b, 10)
    assert b.friendship == 55


def test_potion_at_high_band(store):
    b = store.add_to_bag(1)
    b.friendship = 85
    b.friendship_xp = 0
    store.save_active_buddy(b)
    store.bump_friendship_points(b, 10)
    assert b.friendship == 95


def test_potion_cannot_push_past_the_cap(store):
    b = store.add_to_bag(1)
    b.friendship = 95
    b.friendship_xp = 0
    store.save_active_buddy(b)
    store.bump_friendship_points(b, 50)
    assert b.friendship == 100
