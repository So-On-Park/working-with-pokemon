"""파티가 가득 찼을 때 교체 — pick who steps out, don't send the user away.

Adding a 4th buddy used to dead-end with "다른 포켓몬을 먼저 제외해 주세요".
Now the bag panel offers a picker and swaps in place."""

from __future__ import annotations

import os

import pytest


def _party_of(store, n):
    """Fill the party with `n` fresh buddies and return their bag_ids."""
    ids = []
    for dex in (1, 4, 7)[:n]:
        b = store.add_to_bag(dex, is_rare=False, caught_with="pokeball.basic")
        ids.append(b.bag_id)
    store.save_active_party(ids)
    return ids


def test_party_is_capped_at_three(store):
    ids = _party_of(store, 3)
    extra = store.add_to_bag(25, is_rare=False)
    assert store.add_to_party(extra.bag_id) is False
    assert store.load_active_party() == ids


def test_swap_keeps_the_slot(store):
    """Swapping the middle member must not reorder the others."""
    a, b, c = _party_of(store, 3)
    incoming = store.add_to_bag(25, is_rare=False).bag_id
    assert store.swap_into_party(b, incoming) is True
    assert store.load_active_party() == [a, incoming, c]


def test_swapping_the_leader_promotes_the_newcomer(store):
    """Slot 0 is the 대표 — a remove-then-append would have demoted the
    incoming buddy to the back instead."""
    a, b, c = _party_of(store, 3)
    incoming = store.add_to_bag(25, is_rare=False).bag_id
    assert store.swap_into_party(a, incoming) is True
    party = store.load_active_party()
    assert party == [incoming, b, c]
    # The singular pointer mirrors slot 0.
    assert store.get_meta("active_bag_id") == str(incoming)


def test_swap_rejects_nonsense(store):
    a, b, c = _party_of(store, 3)
    outsider = store.add_to_bag(25, is_rare=False).bag_id
    # Target isn't in the party.
    assert store.swap_into_party(outsider, a) is False
    # Incoming is already in the party.
    assert store.swap_into_party(a, b) is False
    # No such bag entry.
    assert store.swap_into_party(a, 999_999) is False
    assert store.load_active_party() == [a, b, c]


def test_swapped_out_buddy_is_still_owned(store):
    """교체 is not 박사에게 보내기 — leaves the party, not the bag."""
    a, b, c = _party_of(store, 3)
    incoming = store.add_to_bag(25, is_rare=False).bag_id
    store.swap_into_party(b, incoming)
    assert store.get_bag_entry(b) is not None
    assert store.party_slot(b) is None


# ---- the picker renders bag rows, not just on-screen agents ----

@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_picker_lists_every_party_member(qapp, store, temp_assets, no_network):
    from PySide6.QtWidgets import QLabel, QPushButton
    from pokemon_buddy.buddy_picker import BuddyPickerDialog

    ids = _party_of(store, 3)
    members = [store.get_bag_entry(i) for i in ids]
    dlg = BuddyPickerDialog(
        [(b, "showdown") for b in members],
        "누구를 교체할까?", title="파티 교체", action_label="교체",
    )
    try:
        labels = [w.text() for w in dlg.findChildren(QLabel)]
        for b in members:
            assert b.display_name in labels
        buttons = [w.text() for w in dlg.findChildren(QPushButton)]
        assert buttons.count("교체") == 3
        assert "취소" in buttons

        dlg._pick(1)
        assert dlg.chosen_index == 1
    finally:
        dlg.close()
