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


def test_catcher_skill_registered():
    from pokemon_buddy import skills
    sk = skills.find(skills.SKILL_CATCHER)
    assert sk is not None and sk.name == "명포수"
    # learnable/sendable via its teaching scroll
    assert skills.skill_for_item("skill.catcher") is sk
    from pokemon_buddy.items import find as find_item
    assert find_item("skill.catcher") is not None
