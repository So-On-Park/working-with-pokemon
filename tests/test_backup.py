"""Backup / restore round-trip + safety checks."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from pokemon_buddy import backup


@pytest.fixture
def populated_store(store, temp_assets):
    """A store with a few interesting rows + matching custom-pokemon
    sprite files in the temp assets dir. Returns the Store instance."""
    # DB content
    store.set_meta("adventurer_name", "테스트모험가")
    store.add_to_bag(25)  # piㅏ카츄
    store.record_catch(25, "피카츄")
    store.add_item("special.potion", 3)
    # A faux custom-pokemon sprite
    sprite = temp_assets / "9001_bw.gif"
    sprite.write_bytes(b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00"
                       b"\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00"
                       b"\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
    (temp_assets / "custom_pokemon.json").write_text(
        '{"next_id": 9002, "entries": {"9001": {"name_ko": "테스트몬"}}}',
        encoding="utf-8",
    )
    return store


def test_backup_writes_zip_with_manifest(populated_store, tmp_path):
    dest = tmp_path / "backup.zip"
    info = backup.create_backup(dest)
    assert dest.exists()
    assert info["byte_size"] > 0
    assert info["file_count"] >= 1
    # Manifest content survives
    with zipfile.ZipFile(dest, "r") as zf:
        assert backup.MANIFEST_NAME in zf.namelist()
        data = json.loads(zf.read(backup.MANIFEST_NAME).decode("utf-8"))
        assert data["version"] == backup.BACKUP_VERSION
        assert data["app"] == "pokemon-buddy"


def test_backup_bundles_db_and_custom_assets(populated_store, tmp_path):
    dest = tmp_path / "backup.zip"
    backup.create_backup(dest)
    with zipfile.ZipFile(dest, "r") as zf:
        names = set(zf.namelist())
    # DB
    assert any(n.startswith("data/") and n.endswith(".db") for n in names)
    # Custom sprite + registry
    assert "assets/9001_bw.gif" in names
    assert "assets/custom_pokemon.json" in names


def test_backup_skips_vanilla_pokeapi_sprites(populated_store, tmp_path, temp_assets):
    # Drop a vanilla-style file in too
    (temp_assets / "0001_bw.gif").write_bytes(b"GIF89a vanilla")
    dest = tmp_path / "backup.zip"
    backup.create_backup(dest)
    with zipfile.ZipFile(dest, "r") as zf:
        names = set(zf.namelist())
    assert "assets/0001_bw.gif" not in names, (
        "Vanilla PokeAPI sprites should be excluded — they're re-downloadable"
    )


def test_inspect_returns_manifest(populated_store, tmp_path):
    dest = tmp_path / "backup.zip"
    backup.create_backup(dest)
    info = backup.inspect_backup(dest)
    assert info is not None
    assert info["version"] == backup.BACKUP_VERSION


def test_inspect_rejects_non_backup_zip(tmp_path):
    bogus = tmp_path / "not-a-backup.zip"
    with zipfile.ZipFile(bogus, "w") as zf:
        zf.writestr("random.txt", "hello")
    assert backup.inspect_backup(bogus) is None


def test_inspect_rejects_non_zip(tmp_path):
    plain = tmp_path / "plain.txt"
    plain.write_text("this is not a zip")
    assert backup.inspect_backup(plain) is None


def test_restore_round_trip(populated_store, tmp_path, temp_assets, temp_db, monkeypatch):
    """Create a backup, mutate state, restore — original values come back."""
    # The DB lives at tmp_path/test.db (see temp_db fixture). Tell backup
    # to bundle that single file by pointing DATA_DIR at its directory,
    # and stash the archive somewhere disjoint to avoid mid-restore reads.
    monkeypatch.setattr(backup, "DATA_DIR", temp_db.parent)
    monkeypatch.setattr(backup, "ASSETS_DIR", temp_assets)
    archive_dir = tmp_path.parent / "archive"
    archive_dir.mkdir(exist_ok=True)
    dest = archive_dir / "backup.zip"
    backup.create_backup(dest)

    # Mutate after backup
    populated_store.set_meta("adventurer_name", "다른이름")
    populated_store.close()

    backup.restore_backup(dest)

    # Re-open Store and check the original values are back
    from pokemon_buddy.state import Store
    s = Store()
    s.set_meta("onboarded", "1")
    assert s.get_meta("adventurer_name") == "테스트모험가"


def test_restore_rejects_zip_slip(tmp_path):
    """A malicious backup with `..` in member names must be rejected."""
    bogus = tmp_path / "evil.zip"
    with zipfile.ZipFile(bogus, "w") as zf:
        zf.writestr(backup.MANIFEST_NAME, json.dumps({
            "version": "1", "app": "pokemon-buddy",
        }))
        zf.writestr("../escaped.txt", "should not land outside ROOT")
    with pytest.raises(ValueError):
        backup.restore_backup(bogus)
