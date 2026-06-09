"""User-created Pokemon. A small JSON registry alongside the sprite cache
that lets the user register their own GIFs as first-class Pokemon — they
get a synthetic dex_id (9001+), join the wild encounter pool, and resolve
their names locally without hitting PokeAPI.

Storage: assets/custom_pokemon.json
  {
    "next_id": 9002,
    "entries": {
      "9001": {"name_ko": "내포켓몬", "name_eng": "mypokemon"}
    }
  }

GIF files are copied into assets/ using the same naming convention as
PokeAPI sprites (`{dex_id:04d}_bw.gif`, `{dex_id:04d}_showdown.gif`) so
the existing sprite-resolution path picks them up without changes."""

from __future__ import annotations

import json
import logging
import shutil
import threading
from pathlib import Path
from typing import Dict, List, Optional

from .config import CUSTOM_SPRITES_DIR, DATA_DIR

log = logging.getLogger(__name__)

# Registry + custom sprites live under data/ (user state) so a distribution
# update that overwrites assets/ keeps the user's creations — see
# config.migrate_user_data().
REGISTRY_PATH = DATA_DIR / "custom_pokemon.json"
# Start well past the PokeAPI dex space (currently ~1025 + variants) so
# synthetic IDs never collide with a real species ID.
FIRST_CUSTOM_DEX_ID = 9001

_lock = threading.Lock()
_cache: Optional[dict] = None


def _empty_registry() -> dict:
    return {"next_id": FIRST_CUSTOM_DEX_ID, "entries": {}}


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    if REGISTRY_PATH.exists():
        try:
            data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "entries" not in data:
                raise ValueError("malformed registry")
            _cache = data
            return _cache
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            log.warning("custom pokemon registry unreadable, starting fresh: %s", exc)
    _cache = _empty_registry()
    return _cache


def _save(data: dict) -> None:
    try:
        REGISTRY_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        log.error("custom pokemon registry save failed: %s", exc)


def reload() -> None:
    """Drop the in-memory cache. Next read re-loads from disk."""
    global _cache
    with _lock:
        _cache = None


def list_dex_ids() -> List[int]:
    """All registered custom dex_ids, sorted."""
    data = _load()
    return sorted(int(k) for k in data["entries"].keys())


def is_custom(dex_id: int) -> bool:
    data = _load()
    return str(dex_id) in data["entries"]


def get_custom_name(dex_id: int) -> Optional[str]:
    """Korean display name for a custom dex_id, or None if not registered."""
    data = _load()
    entry = data["entries"].get(str(dex_id))
    if entry is None:
        return None
    return entry.get("name_ko")


def get_custom_eng_name(dex_id: int) -> Optional[str]:
    data = _load()
    entry = data["entries"].get(str(dex_id))
    if entry is None:
        return None
    return entry.get("name_eng")


def set_display_scale(dex_id: int, scale: float) -> bool:
    """Update display_scale for a registered custom dex_id. Returns True
    if the entry was found and persisted."""
    with _lock:
        data = _load()
        entry = data["entries"].get(str(dex_id))
        if entry is None:
            return False
        entry["display_scale"] = float(scale)
        _save(data)
    return True


def get_display_scale(dex_id: int) -> float:
    """Per-dex display scale multiplier on top of the sprite-widget's
    automatic normalization. 1.0 = stock; >1.0 means draw bigger (used for
    characters that look small after long-edge normalization because of
    their aspect ratio). Non-custom dex_ids and missing entries return 1.0."""
    data = _load()
    entry = data["entries"].get(str(dex_id))
    if entry is None:
        return 1.0
    try:
        return float(entry.get("display_scale", 1.0))
    except (TypeError, ValueError):
        return 1.0


def _sprite_dest(dex_id: int, style: str) -> Path:
    return CUSTOM_SPRITES_DIR / f"{dex_id:04d}_{style}.gif"


def _refuse_prod_assets_under_pytest() -> None:
    """If pytest is running but a fixture forgot to patch this module's
    sprite dir, we'd silently corrupt the user's real sprite cache (we
    actually did, once — 1×1 stub GIFs overwrote senmon/ssony/huni). Fail
    loudly instead."""
    import os
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        return
    real_root = Path(__file__).resolve().parent.parent / "data" / "custom_sprites"
    if CUSTOM_SPRITES_DIR.resolve() == real_root.resolve():
        raise RuntimeError(
            "custom_pokemon.add() under pytest is targeting the real "
            f"sprite dir ({CUSTOM_SPRITES_DIR}). A fixture forgot to "
            "monkeypatch ASSETS_DIR in pokemon_buddy.custom_pokemon."
        )


def _synth_species_info(dex_id: int) -> dict:
    """Deterministic weight/height/gender_rate for a custom pokemon.
    PokeAPI obviously can't serve these for user-created species, so we
    fabricate plausible values seeded by dex_id. Stays stable across
    restarts so a buddy never changes gender between sessions."""
    import random as _r
    rng = _r.Random(dex_id)
    # Weight: 2.0–40.0 kg (covers small critters to medium-large)
    weight = round(rng.uniform(2.0, 40.0), 1)
    # Height: 0.3–1.5 m
    height = round(rng.uniform(0.3, 1.5), 1)
    # Gender rate: 0/1/2/4/6/7/8, weighted toward balanced. Exclude -1
    # (genderless) so customs always have a gender — feels less sterile.
    gender_rate = rng.choices(
        [0, 1, 2, 4, 6, 7, 8],
        weights=[1, 2, 3, 5, 3, 2, 1],
        k=1,
    )[0]
    return {
        "weight_kg": weight,
        "height_m": height,
        "gender_rate": gender_rate,
    }


def get_species_info(dex_id: int) -> Optional[dict]:
    """Synthesised species info for a custom pokemon. Returns None if the
    dex_id isn't registered as a custom. Lazily fills missing fields on
    older entries (registered before this feature existed)."""
    with _lock:
        data = _load()
        entry = data["entries"].get(str(dex_id))
        if entry is None:
            return None
        if "species_info" not in entry:
            # Backfill — older entries didn't carry this. Synthesise once,
            # persist, then return.
            entry["species_info"] = _synth_species_info(dex_id)
            _save(data)
        return entry["species_info"]


def add(name_ko: str,
        gif_base_path: Path,
        gif_extra_path: Optional[Path] = None,
        name_eng: Optional[str] = None,
        display_scale: float = 1.0) -> int:
    """Register a new custom Pokemon. Copies the base GIF into the assets
    dir under the synthetic dex_id, optionally stashes an "extra motion"
    GIF for future use, writes the registry, and returns the new dex_id.
    Raises ValueError if the base GIF is missing/unreadable.

    Custom Pokemon never get rare/shiny variants — they're skipped in the
    encounter rare roll, so we don't generate shiny copies."""
    _refuse_prod_assets_under_pytest()
    base_src = Path(gif_base_path)
    if not base_src.exists():
        raise ValueError(f"기본 GIF를 찾을 수 없어: {base_src}")

    with _lock:
        data = _load()
        dex_id = int(data.get("next_id", FIRST_CUSTOM_DEX_ID))
        # Skip past any collisions (shouldn't happen but cheap insurance).
        while str(dex_id) in data["entries"]:
            dex_id += 1

        # Base GIF doubles as the sprite for every user-facing style. The
        # showdown lookup falls back to bw via get_buddy_sprite_with_fallback
        # if the showdown slot is absent, so we only need one file on disk.
        shutil.copyfile(base_src, _sprite_dest(dex_id, "bw"))

        extra_name: Optional[str] = None
        if gif_extra_path is not None:
            ex_src = Path(gif_extra_path)
            if ex_src.exists():
                # "추가 모션" is registered but not consumed yet — sits in
                # its own slot so we can wire it up to a specific action
                # animation later without re-registering.
                shutil.copyfile(ex_src, _sprite_dest(dex_id, "extra"))
                extra_name = f"{dex_id:04d}_extra.gif"

        data["entries"][str(dex_id)] = {
            "name_ko": name_ko,
            "name_eng": name_eng or f"custom{dex_id}",
            "extra_motion": extra_name,
            "display_scale": float(display_scale),
            "species_info": _synth_species_info(dex_id),
        }
        data["next_id"] = dex_id + 1
        _save(data)

    return dex_id
