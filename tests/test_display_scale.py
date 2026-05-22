"""display_scale unified lookup — custom routes to custom_pokemon, vanilla
routes to display_scale.json, 1.0 set on vanilla clears the override."""

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


def test_vanilla_default_is_1(temp_assets):
    assert display_scale.get(25) == 1.0


def test_set_vanilla_scale_persists(temp_assets):
    display_scale.set_scale(25, 1.3)
    assert display_scale.get(25) == 1.3


def test_set_vanilla_to_1_removes_override(temp_assets):
    display_scale.set_scale(25, 1.3)
    display_scale.set_scale(25, 1.0)
    assert display_scale.get(25) == 1.0
    # File should also not retain the entry
    import json
    p = temp_assets / "display_scale.json"
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
        assert "25" not in data


def test_custom_pokemon_uses_its_own_scale(temp_assets, sample_gif):
    dex_id = custom_pokemon.add("센몬", sample_gif, display_scale=1.5)
    # Unified lookup should pick up the custom registry's value.
    assert display_scale.get(dex_id) == 1.5


def test_set_scale_on_custom_routes_to_custom_registry(temp_assets, sample_gif):
    dex_id = custom_pokemon.add("센몬", sample_gif, display_scale=1.5)
    display_scale.set_scale(dex_id, 1.8)
    # Both APIs should see the new value.
    assert display_scale.get(dex_id) == 1.8
    assert custom_pokemon.get_display_scale(dex_id) == 1.8


def test_vanilla_scale_does_not_leak_into_custom(temp_assets, sample_gif):
    """Setting a vanilla scale at 25 must not affect a custom dex registered
    later, even if the user happened to mention the same number elsewhere."""
    display_scale.set_scale(25, 1.4)
    dex_id = custom_pokemon.add("센몬", sample_gif, display_scale=2.0)
    assert display_scale.get(25) == 1.4
    assert display_scale.get(dex_id) == 2.0
