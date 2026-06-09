"""Pokemon / skill transfer files (.pokeball / .scroll) — round trips."""

from __future__ import annotations

import json

import pytest

from pokemon_buddy import pokemon_transfer as xfer
from pokemon_buddy import skills


@pytest.fixture
def sample_gif(tmp_path):
    p = tmp_path / "tiny.gif"
    p.write_bytes(
        b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00"
        b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00"
        b"\x02\x02D\x01\x00;"
    )
    return p


def test_full_snapshot_round_trip(store, temp_assets, tmp_path):
    # A grown vanilla individual with a nickname + a learned skill.
    b = store.add_to_bag(25, nickname="삐까")
    store.gain_exp(b, 250)            # bump level/exp
    store.bump_friendship_points(b, 40)
    store.learn_skill(b.bag_id, skills.SKILL_COLLECTOR)
    src = store.get_bag_entry(b.bag_id)

    dest = tmp_path / "out.pokeball"
    xfer.export_pokemon(store, b.bag_id, dest, adventurer_name="테스터")
    assert dest.exists()

    # Simulate "sent away": remove the original, then import the file.
    store.remove_from_bag(b.bag_id)
    result = xfer.import_file(store, dest)

    assert result["kind"] == "pokemon"
    assert result["mode"] == "full"
    got = store.get_bag_entry(result["bag_id"])
    assert got.dex_id == 25
    assert got.nickname == "삐까"
    assert got.level == src.level
    assert got.friendship == src.friendship
    assert got.has_skill(skills.SKILL_COLLECTOR)


def test_species_file_imports_as_fresh_catch(store, temp_assets, tmp_path):
    dest = tmp_path / "pikachu.pokeball"
    xfer.build_species_file(dest, dex_id=25, name_ko="피카츄")
    result = xfer.import_file(store, dest)
    assert result["mode"] == "species"
    got = store.get_bag_entry(result["bag_id"])
    assert got.dex_id == 25
    assert got.level == 1          # fresh
    assert got.friendship == 0
    assert got.learned_skills == []


def test_custom_pokemon_round_trip_embeds_sprite(store, temp_assets, sample_gif, tmp_path):
    from pokemon_buddy import custom_pokemon
    dex = custom_pokemon.add("나의몬", sample_gif, name_eng="namon")
    b = store.add_to_bag(dex)
    dest = tmp_path / "custom.pokeball"
    xfer.export_pokemon(store, b.bag_id, dest)

    manifest = xfer.inspect(dest)
    assert manifest["pokemon"]["is_custom"] is True
    import zipfile
    with zipfile.ZipFile(dest) as zf:
        assert "sprite_bw.gif" in zf.namelist()   # GIF embedded


def test_skill_file_round_trip(store, temp_assets, tmp_path):
    dest = tmp_path / "collector.scroll"
    xfer.export_skill(store, "skill.collector", dest)
    before = store.get_item_count("skill.collector")
    result = xfer.import_file(store, dest)
    assert result["kind"] == "skill"
    assert store.get_item_count("skill.collector") == before + 1


def test_inspect_rejects_non_transfer(tmp_path):
    import zipfile
    p = tmp_path / "bogus.pokeball"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("random.txt", "nope")
    assert xfer.inspect(p) is None
    with pytest.raises(ValueError):
        xfer.import_file(None, p)  # store unused before the format check


def test_suggested_filename_format(store):
    b = store.add_to_bag(25, nickname="삐까")
    store.gain_exp(b, 250)
    b = store.get_bag_entry(b.bag_id)
    fname = xfer.suggested_pokemon_filename(b, "모험가")
    assert fname.startswith("삐까_")
    assert fname.endswith(".pokeball")
    assert "_모험가_" in fname
