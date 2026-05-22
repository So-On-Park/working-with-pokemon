"""Store CRUD + party/dex/inventory invariants."""

from __future__ import annotations


def test_fresh_store_creates_a_starter(store):
    bag = store.list_bag()
    assert len(bag) >= 1, "fresh Store should seed at least one buddy"


def test_add_and_get_bag_entry(store):
    b = store.add_to_bag(1, is_rare=False)
    assert b.dex_id == 1
    assert b.is_rare is False
    assert b.level == 1
    assert b.exp == 0
    assert b.friendship == 0

    fetched = store.get_bag_entry(b.bag_id)
    assert fetched is not None
    assert fetched.bag_id == b.bag_id


def test_rename_writes_nickname_history(store):
    b = store.add_to_bag(25)
    store.rename_bag_entry(b.bag_id, "전기쥐")
    refreshed = store.get_bag_entry(b.bag_id)
    assert refreshed.nickname == "전기쥐"
    assert refreshed.display_name == "전기쥐"
    # Removing the nickname is allowed
    store.rename_bag_entry(b.bag_id, None)
    again = store.get_bag_entry(b.bag_id)
    assert again.nickname in (None, "")


def test_party_add_remove_and_limit(store):
    # The starter already occupies slot 0; add up to 3 total.
    b1 = store.add_to_bag(2)
    b2 = store.add_to_bag(3)
    b3 = store.add_to_bag(4)
    assert store.add_to_party(b1.bag_id) is True
    assert store.add_to_party(b2.bag_id) is True
    # 3rd add should succeed if party still has room (starter + 2 = 3).
    # 4th must fail.
    assert store.add_to_party(b3.bag_id) is False, (
        "party should cap at 3"
    )
    assert store.party_slot(b1.bag_id) is not None
    # Remove and verify slot becomes None
    store.remove_from_party(b1.bag_id)
    assert store.party_slot(b1.bag_id) is None


def test_party_minimum_one(store):
    party = store.load_active_party()
    assert party, "party should never be empty after Store init"
    only = party[0]
    # Removing the last party member must be rejected.
    assert store.remove_from_party(only) is False


def test_swap_active_buddy_moves_to_slot_zero(store):
    b = store.add_to_bag(7)
    store.add_to_party(b.bag_id)
    store.swap_active_buddy(b.bag_id)
    assert store.party_slot(b.bag_id) == 0


def test_record_catch_creates_dex_entry(store):
    e = store.record_catch(150, "뮤츠")
    assert e.dex_id == 150
    assert e.count == 1
    # Second catch increments
    e2 = store.record_catch(150, "뮤츠")
    assert e2.count == 2
    # Rare variant is a separate row
    er = store.record_catch(150, "뮤츠", is_rare=True)
    assert er.is_rare is True
    assert er.count == 1


def test_gain_exp_levels_up(store):
    b = store.add_to_bag(1)
    # Level 1 needs 100 EXP to level
    leveled = store.gain_exp(b, 100)
    assert leveled is True
    refreshed = store.get_bag_entry(b.bag_id)
    assert refreshed.level == 2


def test_friendship_xp_accumulates_to_points(store):
    b = store.add_to_bag(1)
    from pokemon_buddy.config import FRIENDSHIP_XP_PER_POINT
    store.bump_friendship(b, FRIENDSHIP_XP_PER_POINT)
    refreshed = store.get_bag_entry(b.bag_id)
    assert refreshed.friendship == 1


def test_bump_friendship_points_caps_at_100(store):
    b = store.add_to_bag(1)
    store.bump_friendship_points(b, 200)
    refreshed = store.get_bag_entry(b.bag_id)
    assert refreshed.friendship == 100


def test_inventory_add_and_consume(store):
    store.add_item("special.potion", 3)
    assert store.consume_item("special.potion", 1) is True
    assert store.consume_item("special.potion", 1) is True
    assert store.consume_item("special.potion", 1) is True
    # No stock left
    assert store.consume_item("special.potion", 1) is False


def test_consume_more_than_stock_fails(store):
    store.add_item("special.potion", 1)
    assert store.consume_item("special.potion", 5) is False
    # Stock should still be intact after a failed consume
    assert store.consume_item("special.potion", 1) is True


def test_remove_from_bag_drops_party_membership(store):
    b1 = store.add_to_bag(50)
    b2 = store.add_to_bag(51)
    store.add_to_party(b1.bag_id)
    store.add_to_party(b2.bag_id)
    assert store.party_slot(b1.bag_id) is not None
    store.remove_from_bag(b1.bag_id)
    # Removed individual should no longer appear in the party list
    assert b1.bag_id not in store.load_active_party()
    # ... and not in the bag either
    assert store.get_bag_entry(b1.bag_id) is None


def test_meta_get_set_default(store):
    assert store.get_meta("nonexistent_key", "fallback") == "fallback"
    store.set_meta("nonexistent_key", "real_value")
    assert store.get_meta("nonexistent_key") == "real_value"
