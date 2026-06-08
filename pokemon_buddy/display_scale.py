"""Per-dex display-size override registry.

A unified lookup so any code path (sprite rendering, tray icon, etc.) can
ask "how big should dex_id N be drawn?" without caring whether N is a
PokeAPI vanilla or a user-registered custom.

Two sources:
  1) `assets/display_scale.json` — overrides for any dex_id (mostly vanilla)
  2) `custom_pokemon.json` — custom-pokemon entries carry their own scale

Order of precedence in `get(dex_id)`:
  - if custom: the custom registry's scale (authoritative for custom)
  - else: vanilla override if set
  - else: 1.0

`set_scale(dex_id, scale)` writes to the right place automatically.
Setting scale=1.0 removes the override (revert to default)."""

from __future__ import annotations

import json
import logging
import threading
from typing import Dict

from .config import DATA_DIR

log = logging.getLogger(__name__)

# Lives under data/ (user state) — see config.migrate_user_data().
REGISTRY_PATH = DATA_DIR / "display_scale.json"

_lock = threading.Lock()
_cache: Dict[str, float] | None = None


def _load() -> Dict[str, float]:
    global _cache
    if _cache is not None:
        return _cache
    if REGISTRY_PATH.exists():
        try:
            data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("malformed registry")
            _cache = {str(k): float(v) for k, v in data.items()}
            return _cache
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
            log.warning("display_scale registry unreadable: %s", exc)
    _cache = {}
    return _cache


def _save(data: Dict[str, float]) -> None:
    try:
        REGISTRY_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        log.error("display_scale save failed: %s", exc)


def reload() -> None:
    global _cache
    with _lock:
        _cache = None


def get(dex_id: int) -> float:
    """Resolved display-scale multiplier for `dex_id`. Always returns a
    float; 1.0 means use the sprite widget's default normalization as-is."""
    from . import custom_pokemon
    if custom_pokemon.is_custom(dex_id):
        return custom_pokemon.get_display_scale(dex_id)
    with _lock:
        data = _load()
        v = data.get(str(dex_id))
        if v is None:
            return 1.0
        try:
            return float(v)
        except (TypeError, ValueError):
            return 1.0


def set_scale(dex_id: int, scale: float) -> None:
    """Persist an override for `dex_id`. Custom dex_ids update the custom
    registry; everyone else lands in `display_scale.json`. Passing 1.0
    removes a vanilla override (custom keeps the value verbatim — they
    always carry an explicit scale)."""
    from . import custom_pokemon
    s = float(scale)
    if custom_pokemon.is_custom(dex_id):
        custom_pokemon.set_display_scale(dex_id, s)
        return
    with _lock:
        data = _load()
        key = str(dex_id)
        if abs(s - 1.0) < 0.001:
            data.pop(key, None)
        else:
            data[key] = s
        _save(data)
