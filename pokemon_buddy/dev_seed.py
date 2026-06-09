"""Developer test-data seeding.

Fills a Store with enough content to exercise every feature locally:
  - every inventory item (food / toy / pokéball / special / skill) at a high
    count,
  - the full Gen-1 dex (+ any custom species) marked caught, plus a few rares,
  - a spread of bag individuals across levels and friendship tiers, some
    knowing 수집광.

Invoked from the dev-mode tray action ("🧪 테스트 데이터 채우기") or the
``tools/seed_dev_data.py`` script. Idempotent enough to run repeatedly — it
tops inventory up to MAX and appends a fresh demo party each time."""

from __future__ import annotations

import json
from typing import List, Tuple

from . import custom_pokemon
from . import skills as skills_mod
from .items import ITEMS
from .pokemon_names import get_name_cached
from .state import Store

ITEM_MAX = 999

# (dex_id, level, friendship, is_rare, personality, skill_keys)
_BAG_SPREAD: List[Tuple[int, int, int, bool, str, list]] = [
    (1,   1,   0,   False, "playful", []),
    (4,   16,  30,  False, "brave",   []),
    (7,   30,  60,  False, "calm",    []),
    (133, 20,  80,  False, "naive",   []),
    (25,  50,  100, False, "playful", [skills_mod.SKILL_COLLECTOR]),
    (143, 70,  100, False, "calm",    [skills_mod.SKILL_COLLECTOR]),
    (6,   55,  90,  True,  "brave",   []),
    (94,  40,  70,  False, "smart",   []),
]


def _name(dex_id: int) -> str:
    return get_name_cached(dex_id) or f"#{dex_id:04d}"


def seed_test_data(store: Store) -> dict:
    """Populate `store` with broad test content. Returns a summary dict."""
    # 1) Inventory — top every item up to ITEM_MAX.
    for it in ITEMS:
        have = store.get_item_count(it.key)
        if have < ITEM_MAX:
            store.add_item(it.key, ITEM_MAX - have)

    # 2) Dex — every Gen-1 species + customs caught, plus a few rares.
    dex_filled = 0
    for dex in range(1, 152):
        store.record_catch(dex, _name(dex), is_rare=False)
        dex_filled += 1
    for dex in custom_pokemon.list_dex_ids():
        store.record_catch(dex, custom_pokemon.get_custom_name(dex) or _name(dex))
        dex_filled += 1
    for dex in (6, 25, 150):
        store.record_catch(dex, _name(dex), is_rare=True)

    # 3) Bag — a spread of levels / friendship / skills.
    added = 0
    spread = list(_BAG_SPREAD)
    customs = custom_pokemon.list_dex_ids()
    if customs:
        spread.append((customs[0], 25, 100, False, "playful",
                       [skills_mod.SKILL_COLLECTOR]))
    for dex, level, friendship, is_rare, personality, skill_keys in spread:
        store.import_bag_entry(
            dex_id=dex, is_rare=is_rare, level=level, friendship=friendship,
            personality=personality,
            skills=json.dumps([str(s) for s in skill_keys], ensure_ascii=False),
        )
        added += 1

    # A Lv.100 champion that knows BOTH skills, placed in the party so 명포수
    # auto-catch + 수집광 magnetize can be tested right away. Added only once
    # (skip if some bag member already knows 명포수) so repeat seeding doesn't
    # pile up duplicates.
    has_catcher = any(b.has_skill(skills_mod.SKILL_CATCHER)
                      for b in store.list_bag())
    champion_added = False
    if not has_catcher:
        champ = store.import_bag_entry(
            dex_id=6, is_rare=False, level=100, friendship=100,
            nickname="챔프", personality="brave",
            skills=json.dumps([skills_mod.SKILL_COLLECTOR,
                               skills_mod.SKILL_CATCHER], ensure_ascii=False),
        )
        added += 1
        champion_added = True
        # Make sure it's actually on screen (party) so the skills fire.
        if not store.add_to_party(champ.bag_id):
            store.swap_active_buddy(champ.bag_id)

    return {"items_maxed": len(ITEMS), "dex_filled": dex_filled,
            "bag_added": added, "champion_added": champion_added}
