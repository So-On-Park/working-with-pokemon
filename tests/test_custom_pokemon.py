"""custom_pokemon registry — registration, GIF copy, lookups, scale."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from pokemon_buddy import custom_pokemon


@pytest.fixture
def sample_gif(tmp_path):
    """Tiny valid GIF (1x1, single frame). Bytes from the GIF89a minimum."""
    p = tmp_path / "tiny.gif"
    p.write_bytes(
        b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00"
        b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00"
        b"\x02\x02D\x01\x00;"
    )
    return p


def test_empty_registry_lists_nothing(temp_assets):
    assert custom_pokemon.list_dex_ids() == []
    assert custom_pokemon.is_custom(9999) is False
    assert custom_pokemon.get_custom_name(9999) is None
    assert custom_pokemon.get_display_scale(9999) == 1.0


def test_add_assigns_9001_then_increments(temp_assets, sample_gif):
    d1 = custom_pokemon.add("센몬", sample_gif, name_eng="senmon")
    d2 = custom_pokemon.add("쏘니", sample_gif, name_eng="ssony")
    d3 = custom_pokemon.add("후니", sample_gif, name_eng="huni")
    assert d1 == 9001
    assert d2 == 9002
    assert d3 == 9003


def test_add_copies_gif_to_assets(temp_assets, sample_gif):
    dex_id = custom_pokemon.add("센몬", sample_gif)
    bw = temp_assets / f"{dex_id:04d}_bw.gif"
    assert bw.exists()
    assert bw.read_bytes() == sample_gif.read_bytes()
    # No shiny variants for custom — they're never picked by the rare roll.
    assert not (temp_assets / f"{dex_id:04d}_bw_shiny.gif").exists()
    assert not (temp_assets / f"{dex_id:04d}_showdown_shiny.gif").exists()


def test_add_with_extra_motion_creates_extra_gif(temp_assets, sample_gif, tmp_path):
    extra = tmp_path / "extra.gif"
    shutil.copy(sample_gif, extra)
    dex_id = custom_pokemon.add(
        "센몬", sample_gif, gif_extra_path=extra
    )
    assert (temp_assets / f"{dex_id:04d}_extra.gif").exists()


def test_add_raises_on_missing_base_gif(temp_assets, tmp_path):
    bogus = tmp_path / "nope.gif"
    with pytest.raises(ValueError):
        custom_pokemon.add("센몬", bogus)


def test_add_persists_display_scale(temp_assets, sample_gif):
    dex_id = custom_pokemon.add(
        "센몬", sample_gif, display_scale=1.5
    )
    assert custom_pokemon.get_display_scale(dex_id) == 1.5


def test_set_display_scale_updates_registry(temp_assets, sample_gif):
    dex_id = custom_pokemon.add("센몬", sample_gif)
    assert custom_pokemon.set_display_scale(dex_id, 1.8) is True
    assert custom_pokemon.get_display_scale(dex_id) == 1.8


def test_set_display_scale_unknown_dex_is_noop(temp_assets):
    assert custom_pokemon.set_display_scale(99999, 1.5) is False


def test_lookups_after_add(temp_assets, sample_gif):
    dex_id = custom_pokemon.add(
        "센몬", sample_gif, name_eng="senmon"
    )
    assert custom_pokemon.is_custom(dex_id) is True
    assert custom_pokemon.get_custom_name(dex_id) == "센몬"
    assert custom_pokemon.get_custom_eng_name(dex_id) == "senmon"
    assert dex_id in custom_pokemon.list_dex_ids()


def test_registry_survives_reload(temp_assets, sample_gif):
    custom_pokemon.add("센몬", sample_gif)
    custom_pokemon.reload()  # drop in-memory cache
    ids = custom_pokemon.list_dex_ids()
    assert ids == [9001]
    assert custom_pokemon.get_custom_name(9001) == "센몬"
