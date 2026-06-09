"""Developer test-data seeding fills inventory, dex, and bag."""

from __future__ import annotations

from pokemon_buddy import dev_seed
from pokemon_buddy import skills
from pokemon_buddy.dev_seed import ITEM_MAX, GROUP_MAX
from pokemon_buddy.items import ITEMS, ItemKind


def test_seed_maxes_special_and_caps_food_toy(store, temp_assets):
    dev_seed.seed_test_data(store)
    # special / skill / pokeball: each maxed
    for it in ITEMS:
        if it.kind in (ItemKind.FOOD, ItemKind.TOY):
            continue
        assert store.get_item_count(it.key) >= ITEM_MAX
    assert store.get_item_count("skill.collector") >= ITEM_MAX
    # food / toy: KIND total capped around GROUP_MAX (not 999 × variants)
    for kind in (ItemKind.FOOD, ItemKind.TOY):
        total = store.total_of_kind(kind.value)
        assert 0 < total <= GROUP_MAX


def test_seed_fills_full_gen1_dex(store, temp_assets):
    summary = dev_seed.seed_test_data(store)
    assert summary["dex_filled"] >= 151
    # normal + rare for every Gen-1 species
    for dex in (1, 25, 151):
        assert store.get_dex_entry(dex, is_rare=False) is not None
    for dex in range(1, 152):
        assert store.get_dex_entry(dex, is_rare=True) is not None


def test_seed_adds_varied_bag_with_skills(store, temp_assets):
    before = len(store.list_bag())
    summary = dev_seed.seed_test_data(store)
    bag = store.list_bag()
    assert len(bag) == before + summary["bag_added"]
    levels = {b.level for b in bag}
    friendships = {b.friendship for b in bag}
    # a spread of levels and friendship tiers
    assert max(levels) >= 50
    assert 100 in friendships and 0 in friendships
    # at least one individual knows 수집광
    assert any(b.has_skill(skills.SKILL_COLLECTOR) for b in bag)


def test_seed_adds_lv100_catcher_champion_in_party(store, temp_assets):
    dev_seed.seed_test_data(store)
    champs = [b for b in store.list_bag()
              if b.has_skill(skills.SKILL_CATCHER)]
    assert champs, "expected a 명포수 champion"
    champ = champs[0]
    assert champ.level == 100
    assert champ.has_skill(skills.SKILL_COLLECTOR)
    # On screen so the skills actually fire.
    assert store.party_slot(champ.bag_id) is not None


def test_seed_is_repeatable(store, temp_assets):
    dev_seed.seed_test_data(store)
    # running again shouldn't blow up or push food/toy totals over the cap
    dev_seed.seed_test_data(store)
    assert store.get_item_count("special.potion") >= ITEM_MAX
    assert 0 < store.total_of_kind("food") <= GROUP_MAX
