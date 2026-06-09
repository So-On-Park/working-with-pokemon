"""Skill learning (수집광) + user-data migration (data/ relocation)."""

from __future__ import annotations

import json

import pytest

from pokemon_buddy import skills


def test_skill_catalog_maps_scroll_to_skill():
    sk = skills.skill_for_item("skill.collector")
    assert sk is not None
    assert sk.key == skills.SKILL_COLLECTOR
    assert sk.name == "수집광"
    # Non-scroll items grant no skill.
    assert skills.skill_for_item("special.potion") is None


def test_learn_skill_persists_and_is_idempotent(store):
    buddy = store.load_active_buddy()
    assert buddy.learned_skills == []
    assert buddy.has_skill(skills.SKILL_COLLECTOR) is False

    assert store.learn_skill(buddy.bag_id, skills.SKILL_COLLECTOR) is True
    # Learning the same skill again is a no-op (returns False).
    assert store.learn_skill(buddy.bag_id, skills.SKILL_COLLECTOR) is False

    refreshed = store.get_bag_entry(buddy.bag_id)
    assert refreshed.has_skill(skills.SKILL_COLLECTOR) is True
    assert refreshed.learned_skills == [skills.SKILL_COLLECTOR]


def test_learn_skill_unknown_bag_id_is_safe(store):
    assert store.learn_skill(999999, skills.SKILL_COLLECTOR) is False


def test_buddy_learned_skills_handles_garbage(store):
    buddy = store.load_active_buddy()
    # Corrupt the column directly — learned_skills should degrade to [].
    store.conn.execute("UPDATE bag SET skills=? WHERE id=?",
                       ("not json", buddy.bag_id))
    store.conn.commit()
    again = store.get_bag_entry(buddy.bag_id)
    assert again.learned_skills == []


def test_migrate_user_data_copies_assets_into_data(tmp_path, monkeypatch):
    import pokemon_buddy.config as cfg

    assets = tmp_path / "assets"
    data = tmp_path / "data"
    custom_sprites = data / "custom_sprites"
    assets.mkdir()
    data.mkdir()
    custom_sprites.mkdir()
    monkeypatch.setattr(cfg, "ASSETS_DIR", assets)
    monkeypatch.setattr(cfg, "DATA_DIR", data)
    monkeypatch.setattr(cfg, "CUSTOM_SPRITES_DIR", custom_sprites)

    # Seed an old-style install: user files living in assets/.
    (assets / "custom_pokemon.json").write_text(
        json.dumps({"next_id": 9002, "entries": {"9001": {"name_ko": "씨앗몬"}}}),
        encoding="utf-8",
    )
    (assets / "display_scale.json").write_text('{"25": 1.5}', encoding="utf-8")
    (assets / "9001_bw.gif").write_bytes(b"GIF89a custom")
    (assets / "0025_bw.gif").write_bytes(b"GIF89a vanilla")  # must NOT move

    cfg.migrate_user_data()

    # Copied (non-destructive: source still present).
    assert (data / "custom_pokemon.json").exists()
    assert (assets / "custom_pokemon.json").exists()
    assert (data / "display_scale.json").exists()
    assert (custom_sprites / "9001_bw.gif").exists()
    # Vanilla sprite is re-downloadable → left in assets, not relocated.
    assert not (custom_sprites / "0025_bw.gif").exists()


def test_migrate_relocates_legacy_install_for_existing_users(tmp_path, monkeypatch):
    """Frozen update path: an existing user's data lived next to the old .exe
    (data/ + custom sprites). After updating, that progress must land in the
    new writable ROOT so they keep playing without losing anything."""
    import sys
    import pokemon_buddy.config as cfg

    legacy = tmp_path / "old_install"          # where the old portable exe ran
    (legacy / "data" / "custom_sprites").mkdir(parents=True)
    (legacy / "assets").mkdir(parents=True)
    (legacy / "data" / "buddy.db").write_bytes(b"SQLITE_FAKE")
    (legacy / "data" / "custom_pokemon.json").write_text(
        '{"next_id": 9002, "entries": {"9001": {"name_ko": "옛친구"}}}',
        encoding="utf-8",
    )
    (legacy / "data" / "custom_sprites" / "9001_bw.gif").write_bytes(b"GIF89a old")

    base = tmp_path / "localappdata"           # new %LOCALAPPDATA% home
    data = base / "data"
    assets = base / "assets"
    custom_sprites = data / "custom_sprites"
    for d in (base, data, assets, custom_sprites):
        d.mkdir(parents=True)

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(cfg, "INSTALL_DIR", legacy)
    monkeypatch.setattr(cfg, "ROOT", base)
    monkeypatch.setattr(cfg, "DATA_DIR", data)
    monkeypatch.setattr(cfg, "ASSETS_DIR", assets)
    monkeypatch.setattr(cfg, "CUSTOM_SPRITES_DIR", custom_sprites)
    monkeypatch.setattr(cfg, "DB_PATH", data / "buddy.db")

    cfg.migrate_user_data()

    assert (data / "buddy.db").read_bytes() == b"SQLITE_FAKE"
    assert (data / "custom_pokemon.json").exists()
    assert (custom_sprites / "9001_bw.gif").read_bytes() == b"GIF89a old"
    # Source left intact (non-destructive copy).
    assert (legacy / "data" / "buddy.db").exists()


def test_migrate_user_data_does_not_clobber_existing(tmp_path, monkeypatch):
    import pokemon_buddy.config as cfg

    assets = tmp_path / "assets"
    data = tmp_path / "data"
    custom_sprites = data / "custom_sprites"
    for d in (assets, data, custom_sprites):
        d.mkdir()
    monkeypatch.setattr(cfg, "ASSETS_DIR", assets)
    monkeypatch.setattr(cfg, "DATA_DIR", data)
    monkeypatch.setattr(cfg, "CUSTOM_SPRITES_DIR", custom_sprites)

    (assets / "display_scale.json").write_text('{"25": 1.5}', encoding="utf-8")
    # data/ already has the user's authoritative copy — must win.
    (data / "display_scale.json").write_text('{"25": 2.0}', encoding="utf-8")

    cfg.migrate_user_data()

    assert json.loads((data / "display_scale.json").read_text())["25"] == 2.0
