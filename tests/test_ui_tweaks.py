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
