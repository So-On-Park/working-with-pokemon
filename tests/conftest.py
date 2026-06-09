"""Shared fixtures: keep tests offline and isolated from the user's real
DB / assets folder. Every test gets a fresh temp dir + caches reset."""

from __future__ import annotations

import pytest
import requests


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    # state.py captured DB_PATH at import time via `from .config import DB_PATH`,
    # so we patch the module-local symbol as well as the source.
    import pokemon_buddy.config as cfg
    import pokemon_buddy.state as state_mod
    monkeypatch.setattr(cfg, "DB_PATH", db_path)
    monkeypatch.setattr(state_mod, "DB_PATH", db_path)
    return db_path


@pytest.fixture
def store(temp_db):
    """Tests run as if the user has already completed onboarding — the
    fixture flips the `onboarded` meta and re-runs the seed so the bag
    isn't empty. Tests that need to observe the fresh-install state
    should use `unonboarded_store` instead."""
    from pokemon_buddy.state import Store
    s = Store()
    s.set_meta("onboarded", "1")
    s._ensure_active_buddy()
    return s


@pytest.fixture
def unonboarded_store(temp_db):
    """A Store as it exists immediately after a brand-new install:
    no `onboarded` meta, empty bag. BuddyApp's onboarding flow is
    expected to seed the first buddy."""
    from pokemon_buddy.state import Store
    return Store()


@pytest.fixture
def temp_assets(tmp_path, monkeypatch):
    """Redirect every registry to a clean temp dir + invalidate any cache
    that was already populated from the real assets folder."""
    assets = tmp_path / "assets"
    assets.mkdir()
    import pokemon_buddy.config as cfg
    import pokemon_buddy.custom_pokemon as cp
    import pokemon_buddy.display_scale as ds
    import pokemon_buddy.pokemon_names as pn
    import pokemon_buddy.pokemon_info as pi

    monkeypatch.setattr(cfg, "ASSETS_DIR", assets)
    monkeypatch.setattr(cfg, "DATA_DIR", assets)
    monkeypatch.setattr(cfg, "CUSTOM_SPRITES_DIR", assets)
    monkeypatch.setattr(cfg, "BUNDLED_ASSETS_DIR", assets)
    # `from .config import ...` captured bindings at import time — patch the
    # per-module copies too so registries / sprite copies / lookups land in
    # the temp dir, not the user's real folders. Custom sprites + registries
    # now live under data/ (see config.migrate_user_data); we point them all
    # at the single temp dir so the existing path assertions still hold.
    monkeypatch.setattr(cp, "CUSTOM_SPRITES_DIR", assets)
    monkeypatch.setattr(cp, "DATA_DIR", assets)
    import pokemon_buddy.sprites as sp
    monkeypatch.setattr(sp, "ASSETS_DIR", assets)
    monkeypatch.setattr(sp, "CUSTOM_SPRITES_DIR", assets)
    monkeypatch.setattr(sp, "BUNDLED_ASSETS_DIR", assets)
    monkeypatch.setattr(cp, "REGISTRY_PATH", assets / "custom_pokemon.json")
    monkeypatch.setattr(ds, "REGISTRY_PATH", assets / "display_scale.json")
    monkeypatch.setattr(pn, "NAMES_CACHE_PATH", assets / "names_ko.json")
    monkeypatch.setattr(pn, "ENG_NAMES_CACHE_PATH", assets / "names_eng.json")
    monkeypatch.setattr(pi, "INFO_CACHE_PATH", assets / "names_info.json")

    cp.reload()
    ds.reload()
    monkeypatch.setattr(pn, "_cache", None)
    monkeypatch.setattr(pn, "_eng_cache", None)
    monkeypatch.setattr(pi, "_cache", None)

    return assets


@pytest.fixture
def no_network(monkeypatch):
    """Hard-block requests.get so a stray fetch turns into an obvious test
    failure rather than a slow flaky timeout."""
    def _no_get(*a, **kw):
        raise requests.ConnectionError("network disabled in test")
    monkeypatch.setattr(requests, "get", _no_get)
