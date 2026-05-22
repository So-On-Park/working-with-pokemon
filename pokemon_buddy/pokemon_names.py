"""Pokemon Korean-name cache backed by PokeAPI species endpoint.

Offline-first: a missing name silently falls back to `#0XXX`. We never
block the GUI on the network — fetches use a short timeout."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Dict, Optional

import requests

from .config import ASSETS_DIR

log = logging.getLogger(__name__)

NAMES_CACHE_PATH = ASSETS_DIR / "names_ko.json"
ENG_NAMES_CACHE_PATH = ASSETS_DIR / "names_eng.json"
SPECIES_URL = "https://pokeapi.co/api/v2/pokemon-species/{dex_id}/"
REQUEST_TIMEOUT = 4.0

_lock = threading.Lock()
_cache: Optional[Dict[str, str]] = None      # dex_id (str) -> Korean name
_eng_cache: Optional[Dict[str, str]] = None  # dex_id (str) -> English ID name


def _load_cache() -> Dict[str, str]:
    global _cache
    if _cache is not None:
        return _cache
    if NAMES_CACHE_PATH.exists():
        try:
            _cache = json.loads(NAMES_CACHE_PATH.read_text(encoding="utf-8"))
            return _cache
        except (OSError, json.JSONDecodeError) as exc:
            log.debug("names cache read failed: %s", exc)
    _cache = {}
    return _cache


def _save_cache() -> None:
    if _cache is None:
        return
    try:
        NAMES_CACHE_PATH.write_text(
            json.dumps(_cache, ensure_ascii=False, indent=0),
            encoding="utf-8",
        )
    except OSError as exc:
        log.debug("names cache write failed: %s", exc)


def _load_eng_cache() -> Dict[str, str]:
    global _eng_cache
    if _eng_cache is not None:
        return _eng_cache
    if ENG_NAMES_CACHE_PATH.exists():
        try:
            _eng_cache = json.loads(ENG_NAMES_CACHE_PATH.read_text(encoding="utf-8"))
            return _eng_cache
        except (OSError, json.JSONDecodeError) as exc:
            log.debug("eng names cache read failed: %s", exc)
    _eng_cache = {}
    return _eng_cache


def _save_eng_cache() -> None:
    if _eng_cache is None:
        return
    try:
        ENG_NAMES_CACHE_PATH.write_text(
            json.dumps(_eng_cache, ensure_ascii=False, indent=0),
            encoding="utf-8",
        )
    except OSError as exc:
        log.debug("eng names cache write failed: %s", exc)


def fallback_name(dex_id: int) -> str:
    return f"#{dex_id:04d}"


def get_name_cached(dex_id: int) -> Optional[str]:
    """Return cached name if present, else None — never hits the network.
    User-registered custom Pokemon resolve locally and short-circuit the
    PokeAPI cache entirely."""
    from .custom_pokemon import get_custom_name
    custom = get_custom_name(dex_id)
    if custom:
        return custom
    cache = _load_cache()
    return cache.get(str(dex_id))


def fetch_name(dex_id: int) -> Optional[str]:
    """Best-effort blocking fetch. Caches BOTH Korean and English ID names
    from the same response. Returns the Korean name (or None on failure).
    Custom dex_ids skip the network call entirely."""
    from .custom_pokemon import is_custom, get_custom_name
    if is_custom(dex_id):
        return get_custom_name(dex_id)
    cached = get_name_cached(dex_id)
    if cached:
        return cached
    try:
        resp = requests.get(SPECIES_URL.format(dex_id=dex_id), timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return None
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        log.debug("species fetch %d failed: %s", dex_id, exc)
        return None
    eng = data.get("name") or None
    ko = None
    for entry in data.get("names", []):
        lang = entry.get("language", {}).get("name")
        if lang == "ko":
            ko = entry.get("name")
            break
    if not ko and eng:
        ko = eng.capitalize()
    with _lock:
        if ko:
            cache = _load_cache()
            cache[str(dex_id)] = ko
            _save_cache()
        if eng:
            ec = _load_eng_cache()
            ec[str(dex_id)] = eng
            _save_eng_cache()
    return ko


def _fetch_species_data(dex_id: int) -> Optional[dict]:
    try:
        resp = requests.get(SPECIES_URL.format(dex_id=dex_id), timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return None
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        log.debug("species fetch %d failed: %s", dex_id, exc)
        return None


def get_english_name(dex_id: int) -> Optional[str]:
    """Returns the PokeAPI English ID (lowercase, hyphenated). Used to build
    Pokemon Showdown sprite URLs. Custom dex_ids return their registered
    English slug locally."""
    from .custom_pokemon import is_custom, get_custom_eng_name
    if is_custom(dex_id):
        return get_custom_eng_name(dex_id)
    cache = _load_eng_cache()
    cached = cache.get(str(dex_id))
    if cached:
        return cached
    # Force a fresh species fetch — `fetch_name` short-circuits on a Korean
    # cache hit and might never populate the English cache otherwise.
    data = _fetch_species_data(dex_id)
    if not data:
        return None
    eng = data.get("name")
    if eng:
        with _lock:
            ec = _load_eng_cache()
            ec[str(dex_id)] = eng
            _save_eng_cache()
        # Opportunistically populate Korean too if we don't have it yet.
        if get_name_cached(dex_id) is None:
            ko = None
            for entry in data.get("names", []):
                if entry.get("language", {}).get("name") == "ko":
                    ko = entry.get("name")
                    break
            if not ko:
                ko = eng.capitalize()
            with _lock:
                c = _load_cache()
                c[str(dex_id)] = ko
                _save_cache()
    return eng


def get_name(dex_id: int) -> str:
    """Return cached name, else fetch, else fallback. Never raises."""
    name = get_name_cached(dex_id)
    if name:
        return name
    fetched = fetch_name(dex_id)
    return fetched if fetched else fallback_name(dex_id)
