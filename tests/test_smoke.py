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


def test_version_is_single_source_of_truth():
    """pokemon_buddy.__version__ is what the UI shows (tray menu header,
    tooltip, HelpDialog title); installer.iss must carry the same number or
    the installed app and Add/Remove Programs disagree about the version."""
    import re
    from pathlib import Path

    import pokemon_buddy

    assert re.fullmatch(r"\d+\.\d+\.\d+", pokemon_buddy.__version__)

    root = Path(__file__).resolve().parents[1]

    iss = root / "installer.iss"
    m = re.search(r'#define MyAppVersion "([^"]+)"',
                  iss.read_text(encoding="utf-8"))
    assert m is not None, "MyAppVersion not found in installer.iss"
    assert m.group(1) == pokemon_buddy.__version__

    # The README release badge is the third place the number lives — it
    # silently drifted a whole release behind once, so pin it too.
    readme = root / "README.md"
    m = re.search(r"badge/Release-v([\d.]+)-",
                  readme.read_text(encoding="utf-8"))
    assert m is not None, "release badge not found in README.md"
    assert m.group(1) == pokemon_buddy.__version__

    # …and CHANGELOG must have a section for the version being shipped.
    # It is deliberately untracked (balance numbers stay private), so a
    # fresh clone simply won't have it — only check when it's present.
    changelog_path = root / "CHANGELOG.md"
    if changelog_path.exists():
        changelog = changelog_path.read_text(encoding="utf-8")
        assert f"\n## v{pokemon_buddy.__version__}\n" in changelog, (
            f"CHANGELOG.md has no '## v{pokemon_buddy.__version__}' section"
        )
