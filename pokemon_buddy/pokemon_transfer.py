"""Send / receive a Pokemon (or skill) as a single shareable file.

A transfer file is a ZIP container with a friendly extension:
  - ``.pokeball`` — a Pokemon (file association shows a pokéball icon)
  - ``.scroll``   — a skill teaching-scroll (parchment icon)

Inside:
  manifest.json   — what this file holds (see _MANIFEST_* keys below)
  sprite_bw.gif   — custom-pokemon sprite (custom only; vanilla re-downloads)
  sprite_extra.gif

Two pokemon "modes":
  - ``full``    : a complete individual snapshot — every stat travels (level,
                  exp, friendship, personality, gender, nickname, caught_with,
                  learned skills). Produced by the user's 보내기 action. The
                  sender's copy is removed by the caller after a successful write.
  - ``species`` : species-only template — no individual data. Importing one
                  creates a FRESH catch (level 1, random basics) just like
                  meeting a wild Pokemon. These ship with the project under
                  ``pokeballs/``.
"""

from __future__ import annotations

import json
import logging
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Optional

from . import custom_pokemon
from . import pokemon_info
from . import pokemon_names
from . import skills as skills_mod
from .config import ASSETS_DIR, BUNDLED_ASSETS_DIR, CUSTOM_SPRITES_DIR
from .items import find as find_item
from .state import Buddy, Store

log = logging.getLogger(__name__)

POKEMON_EXT = ".pokeball"
SKILL_EXT = ".scroll"

_FORMAT = "pokemon-buddy-transfer"
_VERSION = "1"
_MANIFEST_NAME = "manifest.json"


# ---------------------------------------------------------------- helpers ----
def _find_custom_gif(dex_id: int, style: str) -> Optional[Path]:
    """Locate a custom pokemon's GIF across the writable cache, the legacy
    assets dir, and the shipped seed."""
    name = f"{dex_id:04d}_{style}.gif"
    for base in (CUSTOM_SPRITES_DIR, ASSETS_DIR, BUNDLED_ASSETS_DIR):
        p = base / name
        if p.exists():
            return p
    return None


def _sanitize_filename(name: str) -> str:
    """Strip characters Windows forbids in filenames; keep it readable."""
    bad = '<>:"/\\|?*'
    cleaned = "".join("_" if c in bad else c for c in name).strip(" .")
    return cleaned or "pokemon"


def suggested_pokemon_filename(buddy: Buddy, adventurer_name: str) -> str:
    """`이름_레벨_보낸사람_yymmdd.pokeball` for a user-sent individual."""
    date = time.strftime("%y%m%d")
    stem = f"{buddy.display_name}_{buddy.level}_{adventurer_name or '모험가'}_{date}"
    return _sanitize_filename(stem) + POKEMON_EXT


def suggested_skill_filename(skill_name: str) -> str:
    return _sanitize_filename(f"{skill_name}_교본") + SKILL_EXT


# --------------------------------------------------------------- writing -----
def _write_container(dest: Path, manifest: dict,
                     extra_files: Optional[dict] = None) -> None:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(_MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False,
                                               indent=2))
        for arcname, src in (extra_files or {}).items():
            if src is not None and Path(src).exists():
                zf.write(src, arcname=arcname)


def _pokemon_payload(store: Store, buddy: Buddy) -> tuple[dict, dict]:
    """Build the shared (species) part of a pokemon manifest + the sprite
    files dict for custom pokemon."""
    is_custom = custom_pokemon.is_custom(buddy.dex_id)
    name_ko = buddy.name or pokemon_names.get_name(buddy.dex_id)
    if is_custom:
        name_eng = custom_pokemon.get_custom_eng_name(buddy.dex_id) or ""
        scale = custom_pokemon.get_display_scale(buddy.dex_id)
    else:
        name_eng = pokemon_names.get_english_name(buddy.dex_id) or ""
        scale = 1.0
    info = {
        "is_custom": is_custom,
        "dex_id": buddy.dex_id,
        "name_ko": name_ko,
        "name_eng": name_eng,
        "display_scale": scale,
    }
    files: dict = {}
    if is_custom:
        bw = _find_custom_gif(buddy.dex_id, "bw")
        extra = _find_custom_gif(buddy.dex_id, "extra")
        if bw is not None:
            files["sprite_bw.gif"] = bw
        if extra is not None:
            files["sprite_extra.gif"] = extra
    return info, files


def export_pokemon(store: Store, bag_id: int, dest: Path,
                   adventurer_name: str = "") -> dict:
    """Write a FULL individual snapshot to `dest`. Does NOT remove the source
    bag entry — the caller decides (보내기 removes it after a confirmed write).
    Returns a small summary dict."""
    buddy = store.get_bag_entry(bag_id)
    if buddy is None:
        raise ValueError("보낼 포켓몬을 찾을 수 없어")

    info, files = _pokemon_payload(store, buddy)
    gender = buddy.gender or pokemon_info.gender_for(buddy.dex_id, buddy.bag_id)
    info.update({
        "is_rare": buddy.is_rare,
        "nickname": buddy.nickname,
        "nickname_history": buddy.nickname_history or "[]",
        "level": buddy.level,
        "exp": buddy.exp,
        "friendship": buddy.friendship,
        "friendship_xp": buddy.friendship_xp,
        "personality": buddy.personality,
        "gender": gender,
        "caught_with": buddy.caught_with,
        "skills": buddy.learned_skills,
        "caught_at": buddy.caught_at,
    })
    manifest = {
        "format": _FORMAT, "version": _VERSION,
        "kind": "pokemon", "mode": "full",
        "created_at": time.time(),
        "sender": adventurer_name or "",
        "pokemon": info,
    }
    _write_container(Path(dest), manifest, files)
    log.info("exported pokemon bag_id=%d -> %s", bag_id, dest)
    return {"name": buddy.display_name, "path": str(dest)}


def build_species_file(dest: Path, *, dex_id: int,
                       name_ko: Optional[str] = None) -> dict:
    """Write a species-only template (fresh-catch on import). Used to
    pre-generate the shipped `pokeballs/` library."""
    is_custom = custom_pokemon.is_custom(dex_id)
    if is_custom:
        name_ko = name_ko or custom_pokemon.get_custom_name(dex_id) or f"#{dex_id:04d}"
        name_eng = custom_pokemon.get_custom_eng_name(dex_id) or ""
        scale = custom_pokemon.get_display_scale(dex_id)
    else:
        name_ko = name_ko or pokemon_names.get_name(dex_id)
        name_eng = pokemon_names.get_english_name(dex_id) or ""
        scale = 1.0
    info = {
        "is_custom": is_custom, "dex_id": dex_id,
        "name_ko": name_ko, "name_eng": name_eng, "display_scale": scale,
    }
    files: dict = {}
    if is_custom:
        bw = _find_custom_gif(dex_id, "bw")
        extra = _find_custom_gif(dex_id, "extra")
        if bw is not None:
            files["sprite_bw.gif"] = bw
        if extra is not None:
            files["sprite_extra.gif"] = extra
    manifest = {
        "format": _FORMAT, "version": _VERSION,
        "kind": "pokemon", "mode": "species",
        "created_at": time.time(), "pokemon": info,
    }
    _write_container(Path(dest), manifest, files)
    return {"name": name_ko, "path": str(dest)}


def build_skill_file(dest: Path, item_key: str) -> dict:
    """Write a skill teaching-scroll `.scroll` file. No store needed — a scroll
    carries only the skill identity. Used by export_skill (보내기) and to
    pre-generate the shipped `scrolls/` library."""
    skill = skills_mod.skill_for_item(item_key)
    item = find_item(item_key)
    if skill is None or item is None:
        raise ValueError("내보낼 스킬을 찾을 수 없어")
    manifest = {
        "format": _FORMAT, "version": _VERSION,
        "kind": "skill", "created_at": time.time(),
        "skill": {"key": skill.key, "item_key": item_key,
                  "name": skill.name, "description": skill.description},
    }
    _write_container(Path(dest), manifest)
    return {"name": skill.name, "path": str(dest)}


def export_skill(store: Store, item_key: str, dest: Path) -> dict:
    """Write a skill teaching-scroll to a `.scroll` file. Caller removes one
    scroll from inventory after a confirmed write."""
    result = build_skill_file(Path(dest), item_key)
    log.info("exported skill %s -> %s", item_key, dest)
    return result


# --------------------------------------------------------------- reading -----
def inspect(path: Path) -> Optional[dict]:
    """Return the manifest of a transfer file, or None if it isn't one."""
    try:
        with zipfile.ZipFile(path, "r") as zf:
            if _MANIFEST_NAME not in zf.namelist():
                return None
            data = json.loads(zf.read(_MANIFEST_NAME).decode("utf-8"))
        if data.get("format") != _FORMAT:
            return None
        return data
    except (zipfile.BadZipFile, json.JSONDecodeError, OSError, KeyError) as exc:
        log.debug("inspect %s failed: %s", path, exc)
        return None


def _resolve_local_custom(manifest_pokemon: dict, path: Path) -> int:
    """Ensure the incoming custom species exists in the LOCAL custom registry
    and return its local dex_id. Reuses an existing custom with the same
    English name; otherwise registers a new one, extracting the GIF(s)."""
    name_eng = (manifest_pokemon.get("name_eng") or "").strip()
    name_ko = manifest_pokemon.get("name_ko") or "커스텀"
    scale = float(manifest_pokemon.get("display_scale", 1.0) or 1.0)

    if name_eng:
        for did in custom_pokemon.list_dex_ids():
            if (custom_pokemon.get_custom_eng_name(did) or "") == name_eng:
                return did

    with zipfile.ZipFile(path, "r") as zf:
        names = set(zf.namelist())
        if "sprite_bw.gif" not in names:
            raise ValueError("커스텀 포켓몬 파일에 스프라이트가 없어")
        tmpdir = Path(tempfile.mkdtemp(prefix="pkmn_import_"))
        bw_path = tmpdir / "bw.gif"
        bw_path.write_bytes(zf.read("sprite_bw.gif"))
        extra_path = None
        if "sprite_extra.gif" in names:
            extra_path = tmpdir / "extra.gif"
            extra_path.write_bytes(zf.read("sprite_extra.gif"))

    return custom_pokemon.add(
        name_ko=name_ko, gif_base_path=bw_path,
        gif_extra_path=extra_path, name_eng=name_eng or None,
        display_scale=scale,
    )


def import_file(store: Store, path: Path) -> dict:
    """Import a `.pokeball` / `.scroll` file into the store.

    Returns a result dict the app uses to drive the reveal animation:
      pokemon → {kind:'pokemon', bag_id, dex_id, display_name, species_name,
                 is_rare, is_new_dex, mode}
      skill   → {kind:'skill', skill_name, item_label}
    Raises ValueError if the file isn't a valid transfer file."""
    path = Path(path)
    manifest = inspect(path)
    if manifest is None:
        raise ValueError("올바른 포켓몬/스킬 파일이 아니야")

    kind = manifest.get("kind")

    if kind == "skill":
        sk = manifest.get("skill", {})
        item_key = sk.get("item_key")
        item = find_item(item_key) if item_key else None
        if item is None:
            raise ValueError("알 수 없는 스킬 파일이야")
        store.add_item(item_key, 1)
        return {"kind": "skill", "skill_name": sk.get("name", item.label),
                "item_label": item.label}

    if kind != "pokemon":
        raise ValueError("알 수 없는 파일 종류야")

    p = manifest.get("pokemon", {})
    mode = manifest.get("mode", "species")
    is_custom = bool(p.get("is_custom"))
    name_ko = p.get("name_ko") or f"#{int(p.get('dex_id', 0)):04d}"

    dex_id = _resolve_local_custom(p, path) if is_custom else int(p["dex_id"])

    is_rare = bool(p.get("is_rare", False)) if mode == "full" else False
    dex_entry = store.record_catch(dex_id, name_ko, is_rare=is_rare)
    is_new_dex = dex_entry.count == 1

    if mode == "full":
        buddy = store.import_bag_entry(
            dex_id=dex_id, is_rare=is_rare,
            nickname=p.get("nickname"),
            level=int(p.get("level", 1)), exp=int(p.get("exp", 0)),
            friendship=int(p.get("friendship", 0)),
            friendship_xp=int(p.get("friendship_xp", 0)),
            caught_with=p.get("caught_with", "pokeball.basic"),
            personality=p.get("personality", "playful"),
            nickname_history=p.get("nickname_history", "[]"),
            skills=json.dumps([str(s) for s in p.get("skills", [])],
                              ensure_ascii=False),
            gender=p.get("gender"),
            caught_at=p.get("caught_at"),
        )
    else:
        # species-only → fresh catch (random personality/basics, level 1)
        buddy = store.add_to_bag(dex_id, is_rare=False)

    return {
        "kind": "pokemon", "bag_id": buddy.bag_id, "dex_id": dex_id,
        "display_name": buddy.display_name, "species_name": name_ko,
        "is_rare": is_rare, "is_new_dex": is_new_dex, "mode": mode,
    }
