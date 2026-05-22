"""Smoke tests — every public module imports cleanly and the obvious
class / function symbols exist. Catches import-time regressions like
accidental circular imports, missing names after refactors, etc."""

from __future__ import annotations

import importlib

import pytest


MODULES = [
    "pokemon_buddy",
    "pokemon_buddy.app",
    "pokemon_buddy.bag_dialog",
    "pokemon_buddy.buddy_agent",
    "pokemon_buddy.buddy_picker",
    "pokemon_buddy.buddy_popup",
    "pokemon_buddy.config",
    "pokemon_buddy.custom_pokemon",
    "pokemon_buddy.custom_pokemon_dialog",
    "pokemon_buddy.daily_schedule",
    "pokemon_buddy.daily_schedule_dialog",
    "pokemon_buddy.dex_dialog",
    "pokemon_buddy.display_scale",
    "pokemon_buddy.encounter",
    "pokemon_buddy.encounter_window",
    "pokemon_buddy.evolution",
    "pokemon_buddy.evolution_dialog",
    "pokemon_buddy.inventory_dialog",
    "pokemon_buddy.item_drop",
    "pokemon_buddy.items",
    "pokemon_buddy.main_panel",
    "pokemon_buddy.messages",
    "pokemon_buddy.nav_bar",
    "pokemon_buddy.pet_window",
    "pokemon_buddy.pokeball",
    "pokemon_buddy.pokemon_detail_dialog",
    "pokemon_buddy.pokemon_info",
    "pokemon_buddy.pokemon_names",
    "pokemon_buddy.reminder_dialog",
    "pokemon_buddy.reminders",
    "pokemon_buddy.speech_bubble",
    "pokemon_buddy.sprite_widget",
    "pokemon_buddy.sprites",
    "pokemon_buddy.star_burst",
    "pokemon_buddy.state",
    "pokemon_buddy.windows_state",
]


@pytest.mark.parametrize("mod_name", MODULES)
def test_module_imports_cleanly(mod_name):
    importlib.import_module(mod_name)


def test_key_public_symbols_present():
    from pokemon_buddy.app import BuddyApp, main
    from pokemon_buddy.state import Store, Buddy, DexEntry
    from pokemon_buddy.custom_pokemon import add, list_dex_ids
    from pokemon_buddy.display_scale import get, set_scale
    from pokemon_buddy.buddy_popup import (
        ACTION_BAG, ACTION_DETAIL, ACTION_DEX, ACTION_FEED, ACTION_PLAY,
        ACTION_TRAIN, ACTION_RENAME, ACTION_INVENTORY,
    )
    # If we got here, every symbol is reachable.
    assert callable(main)
    assert callable(add)
    assert callable(set_scale)
