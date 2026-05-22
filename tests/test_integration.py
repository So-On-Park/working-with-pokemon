"""Cross-module flows — make sure pieces wire up the way the GUI assumes
they do, without needing PySide6 itself."""

from __future__ import annotations

import pytest

from pokemon_buddy import custom_pokemon, display_scale


@pytest.fixture
def sample_gif(tmp_path):
    p = tmp_path / "tiny.gif"
    p.write_bytes(
        b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00"
        b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00"
        b"\x02\x02D\x01\x00;"
    )
    return p


def test_catch_flow_creates_bag_and_dex(store, temp_assets, no_network):
    """Reproduces on_wild_caught: record_catch + add_to_bag both fire."""
    dex_id, name = 150, "뮤츠"
    entry = store.record_catch(dex_id, name, is_rare=False)
    buddy = store.add_to_bag(dex_id, is_rare=False, caught_with="pokeball.basic")
    assert entry.count == 1
    assert buddy.dex_id == dex_id
    # Catch a second time — bag gets a new individual, dex count bumps.
    entry2 = store.record_catch(dex_id, name, is_rare=False)
    store.add_to_bag(dex_id)
    assert entry2.count == 2
    assert len([b for b in store.list_bag() if b.dex_id == dex_id]) == 2


def test_evolve_preserves_individual_swaps_species(store, temp_assets, no_network):
    """Evolving keeps the same bag_id but rewrites dex_id."""
    base = store.add_to_bag(1)  # 이상해씨
    store.swap_active_buddy(base.bag_id)
    store.evolve_active_buddy(2)  # 이상해풀
    after = store.get_bag_entry(base.bag_id)
    assert after.dex_id == 2
    assert after.bag_id == base.bag_id, "evolution must not reassign bag_id"


def test_custom_pokemon_full_registration_flow(store, temp_assets, no_network, sample_gif):
    """End-to-end mirror of BuddyApp.on_add_custom_pokemon's side-effects."""
    dex_id = custom_pokemon.add("센몬", sample_gif, name_eng="senmon",
                                 display_scale=1.5)
    buddy = store.add_to_bag(dex_id, is_rare=False)
    dex_entry = store.record_catch(dex_id, "센몬", is_rare=False)

    # Registry
    assert custom_pokemon.is_custom(dex_id) is True
    assert custom_pokemon.get_custom_name(dex_id) == "센몬"
    # Sprite file
    assert (temp_assets / f"{dex_id:04d}_bw.gif").exists()
    # Bag
    assert buddy.dex_id == dex_id
    # Dex
    assert dex_entry.count == 1
    # Display scale resolves to the custom registry's value
    assert display_scale.get(dex_id) == 1.5


def test_swap_buddy_promotes_to_primary(store, temp_assets, no_network):
    b1 = store.add_to_bag(10)
    b2 = store.add_to_bag(20)
    store.add_to_party(b1.bag_id)
    store.add_to_party(b2.bag_id)
    # Promote b2 to slot 0
    store.swap_active_buddy(b2.bag_id)
    party = store.load_active_party()
    assert party[0] == b2.bag_id


def test_passive_gain_accumulates_friendship(store, temp_assets, no_network):
    """A single passive tick should credit PASSIVE_EXP toward exp, and
    after FRIENDSHIP_XP_PER_POINT friendship-xp bumps the integer
    friendship goes up by 1."""
    from pokemon_buddy.config import (
        FRIENDSHIP_XP_PER_POINT,
        PASSIVE_FRIENDSHIP_XP,
        PASSIVE_EXP,
    )
    b = store.add_to_bag(1)
    store.gain_exp(b, PASSIVE_EXP)
    after_exp = store.get_bag_entry(b.bag_id)
    assert after_exp.exp == PASSIVE_EXP

    # Friendship XP accumulator → 1 visible point. Refresh buddy each tick
    # because bump_friendship mutates the DB row directly.
    for _ in range(FRIENDSHIP_XP_PER_POINT):
        fresh = store.get_bag_entry(b.bag_id)
        store.bump_friendship(fresh, PASSIVE_FRIENDSHIP_XP)
    refreshed = store.get_bag_entry(b.bag_id)
    assert refreshed.friendship >= 1


def test_party_invariant_after_remove_from_bag(store, temp_assets, no_network):
    """If we drop a party member from the bag, party should not reference
    a ghost bag_id."""
    b = store.add_to_bag(7)
    store.add_to_party(b.bag_id)
    assert b.bag_id in store.load_active_party()
    store.remove_from_bag(b.bag_id)
    assert b.bag_id not in store.load_active_party()


def test_special_item_consume_then_apply(store, temp_assets, no_network):
    """Mirror on_use_item: consume_item must succeed before applying any
    side-effect — and a failed consume must NOT touch the buddy."""
    b = store.add_to_bag(25)
    # No potion in stock yet → consume must fail.
    assert store.consume_item("special.potion", 1) is False
    # Stock + consume + apply (friendship +10)
    store.add_item("special.potion", 1)
    assert store.consume_item("special.potion", 1) is True
    store.bump_friendship_points(b, 10)
    refreshed = store.get_bag_entry(b.bag_id)
    assert refreshed.friendship == 10
