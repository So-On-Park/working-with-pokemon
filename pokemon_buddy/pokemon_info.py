"""Cached species-level data from PokeAPI (weight, height, gender_rate).

Used by the Pokemon detail dialog. Offline-first like everything else:
a missing cache + offline returns None, and callers display a fallback.

The names cache in `pokemon_names.py` predates this module — could be
merged, but kept separate so the detail dialog's heavier fetch (two
endpoints per species) doesn't slow down name lookups."""

from __future__ import annotations

import json
import logging
import threading
from typing import Dict, Optional

import requests

from .config import ASSETS_DIR

log = logging.getLogger(__name__)

INFO_CACHE_PATH = ASSETS_DIR / "species_info.json"
POKEMON_URL = "https://pokeapi.co/api/v2/pokemon/{dex_id}/"
SPECIES_URL = "https://pokeapi.co/api/v2/pokemon-species/{dex_id}/"
REQUEST_TIMEOUT = 4.0

_lock = threading.Lock()
_cache: Optional[Dict[str, dict]] = None


def _load_cache() -> Dict[str, dict]:
    global _cache
    if _cache is not None:
        return _cache
    if INFO_CACHE_PATH.exists():
        try:
            _cache = json.loads(INFO_CACHE_PATH.read_text(encoding="utf-8"))
            return _cache
        except (OSError, json.JSONDecodeError) as exc:
            log.debug("species info cache read failed: %s", exc)
    _cache = {}
    return _cache


def _save_cache() -> None:
    if _cache is None:
        return
    try:
        INFO_CACHE_PATH.write_text(
            json.dumps(_cache, ensure_ascii=False, indent=0),
            encoding="utf-8",
        )
    except OSError as exc:
        log.debug("species info cache write failed: %s", exc)


def get_species_info(dex_id: int) -> Optional[dict]:
    """Returns {weight_kg, height_m, gender_rate} or None.

    `gender_rate` is the PokeAPI convention: -1 for genderless, otherwise
    the chance of being female out of 8 (so 4 = 50/50)."""
    cache = _load_cache()
    key = str(dex_id)
    if key in cache:
        return cache[key]

    try:
        pr = requests.get(POKEMON_URL.format(dex_id=dex_id),
                          timeout=REQUEST_TIMEOUT)
        sr = requests.get(SPECIES_URL.format(dex_id=dex_id),
                          timeout=REQUEST_TIMEOUT)
        if pr.status_code != 200 or sr.status_code != 200:
            return None
        p_data = pr.json()
        s_data = sr.json()
    except (requests.RequestException, ValueError) as exc:
        log.debug("species info fetch %d failed: %s", dex_id, exc)
        return None

    info = {
        "weight_kg": p_data.get("weight", 0) / 10.0,  # hectograms → kg
        "height_m":  p_data.get("height", 0) / 10.0,  # decimeters → m
        "gender_rate": s_data.get("gender_rate", -1),
    }
    with _lock:
        cache[key] = info
        _save_cache()
    return info


def get_weight_kg(dex_id: int) -> Optional[float]:
    info = get_species_info(dex_id)
    return info["weight_kg"] if info else None


def get_height_m(dex_id: int) -> Optional[float]:
    info = get_species_info(dex_id)
    return info["height_m"] if info else None


def get_gender_rate(dex_id: int) -> Optional[int]:
    info = get_species_info(dex_id)
    return info["gender_rate"] if info else None


def gender_for(dex_id: int, bag_id: int) -> str:
    """Resolve a buddy's gender deterministically — same bag_id always
    gives the same result, so refreshes don't flip it. Returns 'm', 'f',
    or 'n' (genderless / unknown)."""
    rate = get_gender_rate(dex_id)
    if rate is None or rate < 0:
        return "n"
    if rate == 0:
        return "m"
    if rate == 8:
        return "f"
    # Seed RNG with bag_id so every load picks the same gender for this
    # individual without a column on disk.
    import random as _r
    rng = _r.Random(bag_id * 31 + dex_id)
    return "f" if rng.randint(0, 7) < rate else "m"
