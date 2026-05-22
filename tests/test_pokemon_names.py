"""pokemon_names lookups + custom_pokemon integration. Network is blocked
via the no_network fixture — these tests verify the offline-first paths
don't accidentally make HTTP calls."""

from __future__ import annotations

import pytest

from pokemon_buddy import custom_pokemon
from pokemon_buddy.pokemon_names import (
    fallback_name,
    fetch_name,
    get_english_name,
    get_name,
    get_name_cached,
)


@pytest.fixture
def sample_gif(tmp_path):
    p = tmp_path / "tiny.gif"
    p.write_bytes(
        b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00"
        b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00"
        b"\x02\x02D\x01\x00;"
    )
    return p


def test_fallback_name_format():
    assert fallback_name(25) == "#0025"
    assert fallback_name(151) == "#0151"


def test_get_name_cached_returns_none_when_empty(temp_assets, no_network):
    assert get_name_cached(25) is None


def test_get_name_cached_returns_custom_name(temp_assets, no_network, sample_gif):
    dex_id = custom_pokemon.add("센몬", sample_gif, name_eng="senmon")
    # Custom dex_id should resolve locally without touching the network.
    assert get_name_cached(dex_id) == "센몬"


def test_fetch_name_short_circuits_for_custom(temp_assets, no_network, sample_gif):
    """fetch_name() normally calls requests.get — but for custom dex_ids
    it has to skip the call entirely. Network is blocked in this fixture,
    so a network attempt would raise."""
    dex_id = custom_pokemon.add("쏘니", sample_gif, name_eng="ssony")
    # Should NOT raise. Returns the custom name.
    name = fetch_name(dex_id)
    assert name == "쏘니"


def test_get_english_name_short_circuits_for_custom(temp_assets, no_network, sample_gif):
    dex_id = custom_pokemon.add("후니", sample_gif, name_eng="huni")
    assert get_english_name(dex_id) == "huni"


def test_get_name_falls_back_when_offline(temp_assets, no_network):
    """Vanilla dex without cache + no network → fallback `#NNNN`."""
    assert get_name(999) == "#0999"


def test_get_name_uses_cache_first(temp_assets, no_network):
    """If a name is already in the json cache, the lookup must not hit
    the network. We seed the cache directly and verify."""
    import json
    import pokemon_buddy.pokemon_names as pn
    pn.NAMES_CACHE_PATH.write_text(
        json.dumps({"25": "피카츄"}, ensure_ascii=False), encoding="utf-8"
    )
    pn.reload() if hasattr(pn, "reload") else None
    # Force a re-read by invalidating the in-memory cache
    pn._cache = None
    assert get_name(25) == "피카츄"
