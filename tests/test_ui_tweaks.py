"""Small UI-behavior tweaks: farewell lines + per-kind drop sizing."""

from __future__ import annotations

from pokemon_buddy import messages
from pokemon_buddy.item_drop import drop_size_for
from pokemon_buddy.config import ITEM_DROP_SIZE_PX, ITEM_DROP_SIZE_SMALL_PX
from pokemon_buddy.items import ItemKind


def test_pick_farewell_returns_known_line():
    line = messages.pick_farewell()
    assert isinstance(line, str) and line
    assert line in messages.FAREWELL


def test_farewell_bank_nonempty():
    assert len(messages.FAREWELL) >= 3


def test_drop_size_small_for_food_toy_ball():
    for kind in (ItemKind.FOOD, ItemKind.TOY, ItemKind.POKEBALL):
        assert drop_size_for(kind) == ITEM_DROP_SIZE_SMALL_PX
    # special + skill keep the larger size
    for kind in (ItemKind.SPECIAL, ItemKind.SKILL):
        assert drop_size_for(kind) == ITEM_DROP_SIZE_PX
    assert ITEM_DROP_SIZE_SMALL_PX < ITEM_DROP_SIZE_PX


def test_collector_and_catcher_lines_nonempty():
    assert messages.pick_collector() in messages.COLLECTOR_LINES
    assert messages.pick_catcher() in messages.CATCHER_LINES
    assert messages.COLLECTOR_LINES and messages.CATCHER_LINES


def test_random_available_of_kind(store, temp_assets):
    store.add_item("food.cake", 1)
    keys = {store.random_available_of_kind("food") for _ in range(30)}
    # only owned foods come back, and more than one variety can appear
    assert keys and all(k.startswith("food.") for k in keys)
    for k in keys:
        assert store.get_item_count(k) > 0
    # a kind with nothing owned → None (no special items by default)
    assert store.random_available_of_kind("special") is None


def test_food_toy_flavor_lines():
    assert messages.pick_food_line("food.apple") in messages.FOOD_LINES["food.apple"]
    assert messages.pick_toy_line("toy.ball") in messages.TOY_LINES["toy.ball"]
    # unknown key falls back to a generic line (non-empty)
    assert messages.pick_food_line("food.unknown")
    assert messages.pick_toy_line("toy.unknown")


def test_catcher_skill_registered():
    from pokemon_buddy import skills
    sk = skills.find(skills.SKILL_CATCHER)
    assert sk is not None and sk.name == "명포수"
    # learnable/sendable via its teaching scroll
    assert skills.skill_for_item("skill.catcher") is sk
    from pokemon_buddy.items import find as find_item
    assert find_item("skill.catcher") is not None
