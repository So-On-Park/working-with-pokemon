"""이로치(shiny) naming rules.

Two invariants, both user-visible:
  1. No name anywhere carries a "레어" prefix — a shiny 피카츄 is 피카츄,
     exactly like in the games. The ✨ marker carries the distinction.
  2. The word 이로치 appears as a title in the detail dialog, and nowhere
     as part of a name.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pokemon_buddy import config
from pokemon_buddy.state import DexEntry


PKG_DIR = Path(__file__).resolve().parent.parent / "pokemon_buddy"


def test_shiny_label_is_irochi():
    assert config.SHINY_LABEL == "이로치"
    # The old prefix constant is gone for good — nothing may reintroduce it.
    assert not hasattr(config, "RARE_NAME_PREFIX")


def test_dex_entry_name_has_no_prefix():
    shiny = DexEntry(dex_id=25, is_rare=True, name="피카츄",
                     first_caught_at=0.0, last_caught_at=0.0, count=1)
    plain = DexEntry(dex_id=25, is_rare=False, name="피카츄",
                     first_caught_at=0.0, last_caught_at=0.0, count=1)
    assert shiny.display_name == "피카츄"
    assert shiny.display_name == plain.display_name


def test_shiny_buddy_keeps_plain_species_name(store):
    shiny = store.add_to_bag(25, is_rare=True, caught_with="pokeball.basic")
    plain = store.add_to_bag(25, is_rare=False, caught_with="pokeball.basic")
    assert shiny.is_rare is True
    assert shiny.species_label == plain.species_label
    assert shiny.display_name == shiny.species_label
    assert "레어" not in shiny.display_name
    assert "이로치" not in shiny.display_name


def test_nickname_still_overrides_for_shiny(store):
    shiny = store.add_to_bag(25, is_rare=True, caught_with="pokeball.basic")
    store.rename_bag_entry(shiny.bag_id, "반짝이")
    refreshed = store.get_bag_entry(shiny.bag_id)
    assert refreshed.display_name == "반짝이"


def test_no_rare_prefix_left_in_package_source():
    """Regression guard — the literal 레어 must not come back anywhere in
    the shipped package (UI strings, docstrings, comments)."""
    offenders = [
        p.name for p in PKG_DIR.glob("*.py")
        if "레어" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []


# ---- detail dialog badge (real widget, offscreen) ----

@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _labels(widget):
    from PySide6.QtWidgets import QLabel
    return [w.text() for w in widget.findChildren(QLabel)]


def test_detail_dialog_titles_shiny_as_irochi(qapp, store, temp_assets,
                                              no_network):
    from pokemon_buddy.pokemon_detail_dialog import PokemonDetailDialog
    shiny = store.add_to_bag(25, is_rare=True, caught_with="pokeball.basic")
    dlg = PokemonDetailDialog(shiny, "showdown")
    try:
        texts = _labels(dlg)
        assert f"✨ {config.SHINY_LABEL}" in texts
        # …and the title is the ONLY place the word shows up.
        assert sum("이로치" in t for t in texts) == 1
    finally:
        dlg.close()


def test_detail_dialog_has_no_badge_for_plain(qapp, store, temp_assets,
                                              no_network):
    from pokemon_buddy.pokemon_detail_dialog import PokemonDetailDialog
    plain = store.add_to_bag(25, is_rare=False, caught_with="pokeball.basic")
    dlg = PokemonDetailDialog(plain, "showdown")
    try:
        assert not any("이로치" in t for t in _labels(dlg))
    finally:
        dlg.close()
