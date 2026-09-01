"""경험치 표시 — the number the UI announces must be the number that
actually landed.

`Store.gain_exp` only ever returned a `leveled` bool, so the 이상한사탕
handler hardcoded "EXP +100" while the friendship bonus was quietly
banking 120 or 150 (and nothing at all at the level cap). These tests pin
the honest-reporting contract."""

from __future__ import annotations

import os

import pytest

from pokemon_buddy.config import (
    FRIENDSHIP_BONUS_HIGH,
    FRIENDSHIP_BONUS_MID,
    MAX_LEVEL,
    exp_to_next_for,
)


def _buddy_at(store, *, friendship=0, level=1, exp=0):
    b = store.add_to_bag(25, is_rare=False, caught_with="pokeball.basic")
    b.friendship = friendship
    b.level = level
    b.exp = exp
    store.save_active_buddy(b)
    return b


def test_gain_exp_detailed_reports_plain_amount(store):
    # Lv.50 needs 300, so 100 lands without tripping a level-up.
    b = _buddy_at(store, friendship=0, level=50)
    gained, leveled = store.gain_exp_detailed(b, 100)
    assert gained == 100
    assert leveled is False
    assert b.exp == 100


def test_gain_exp_detailed_includes_friendship_bonus(store):
    # Lv.50 (needs 300) so even the 1.5x result stays inside one level.
    mid = _buddy_at(store, friendship=FRIENDSHIP_BONUS_MID, level=50)
    gained_mid, _ = store.gain_exp_detailed(mid, 100)
    assert gained_mid == 120
    assert mid.exp == 120

    high = _buddy_at(store, friendship=FRIENDSHIP_BONUS_HIGH, level=50)
    gained_high, _ = store.gain_exp_detailed(high, 100)
    assert gained_high == 150
    assert high.exp == 150


def test_gain_exp_detailed_reports_level_up(store):
    need = exp_to_next_for(50)          # 300
    b = _buddy_at(store, friendship=0, level=50, exp=need - 10)
    gained, leveled = store.gain_exp_detailed(b, 100)
    assert leveled is True
    assert gained == 100
    assert b.level == 51
    assert b.exp == 100 - 10            # carry-over past the threshold


def test_maxed_buddy_banks_nothing_and_says_so(store):
    b = _buddy_at(store, friendship=0, level=MAX_LEVEL, exp=exp_to_next_for(MAX_LEVEL))
    gained, leveled = store.gain_exp_detailed(b, 100)
    # An honest zero — the old code would have claimed +100 here.
    assert gained == 0
    assert leveled is False
    assert b.level == MAX_LEVEL
    assert b.exp == b.exp_to_next


# ---- 이상한사탕 = 레벨 +1 (원작과 동일) ----

def test_rare_candy_raises_level_by_exactly_one(store):
    b = _buddy_at(store, friendship=0, level=28, exp=2)
    assert store.level_up_once(b) is True
    assert b.level == 29
    # Progress resets — it is a level grant, not an EXP grant.
    assert b.exp == 0


def test_rare_candy_ignores_the_friendship_bonus(store):
    """A 1.5x multiplier on "one level" would be meaningless — a maxed-out
    friendship buddy must gain exactly the same single level."""
    plain = _buddy_at(store, friendship=0, level=10, exp=0)
    loved = _buddy_at(store, friendship=FRIENDSHIP_BONUS_HIGH, level=10, exp=0)
    store.level_up_once(plain)
    store.level_up_once(loved)
    assert plain.level == loved.level == 11
    assert plain.exp == loved.exp == 0


def test_rare_candy_into_the_cap_pins_the_bar(store):
    b = _buddy_at(store, friendship=0, level=MAX_LEVEL - 1, exp=0)
    assert store.level_up_once(b) is True
    assert b.level == MAX_LEVEL
    assert b.exp == b.exp_to_next


def test_rare_candy_does_nothing_at_the_cap(store):
    b = _buddy_at(store, friendship=0, level=MAX_LEVEL, exp=exp_to_next_for(MAX_LEVEL))
    assert store.level_up_once(b) is False
    assert b.level == MAX_LEVEL


def test_gain_exp_stays_bool_for_existing_callers(store):
    b = _buddy_at(store, friendship=0, level=1, exp=exp_to_next_for(1) - 1)
    assert store.gain_exp(b, 1) is True
    fresh = _buddy_at(store, friendship=0)
    assert store.gain_exp(fresh, 1) is False


# ---- the bubble the user actually reads ----

@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_level_up_bubble_shows_exp(qapp, store, temp_assets, no_network):
    """A level-up used to print only the new level — the one moment that
    told you nothing about EXP."""
    from pokemon_buddy.buddy_agent import BuddyAgent
    b = _buddy_at(store, friendship=0, level=5, exp=50)
    agent = BuddyAgent(store, b, "showdown", slot_index=0)
    said: list[str] = []
    agent.window.say = lambda text, *a, **kw: said.append(text)
    try:
        agent._after_level_up()
    finally:
        agent.window.close()
    assert len(said) == 1
    assert "Lv.5" in said[0]
    assert f"EXP 50/{exp_to_next_for(5)}" in said[0]
