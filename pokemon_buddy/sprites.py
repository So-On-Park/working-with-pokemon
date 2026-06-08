"""Sprite acquisition and caching. Offline-first: cached files are used
whenever present, and missing files are downloaded only opportunistically.

The user-facing sprite styles are only `bw` (도트) and `showdown` (쇼다운).
Each pairs with a shiny variant on disk — but those are not user selectable.
They're picked automatically when a Pokemon's `is_rare` flag is set."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Iterable, Optional

import requests

from .config import ASSETS_DIR, BUNDLED_ASSETS_DIR, CUSTOM_SPRITES_DIR

log = logging.getLogger(__name__)

# PokeAPI animated Gen 5 BW
BW_URL = (
    "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/"
    "versions/generation-v/black-white/animated/{dex_id}.gif"
)
BW_SHINY_URL = (
    "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/"
    "versions/generation-v/black-white/animated/shiny/{dex_id}.gif"
)
# Pokemon Showdown animated sprites — higher detail, all gens
SHOWDOWN_URL = "https://play.pokemonshowdown.com/sprites/ani/{name}.gif"
SHOWDOWN_SHINY_URL = "https://play.pokemonshowdown.com/sprites/ani-shiny/{name}.gif"
# Static pixel fallback (Gen 8 official sprite)
PIXEL_PNG_URL = (
    "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/"
    "{dex_id}.png"
)
# 3D-rendered Pokemon HOME — kept for the tray icon fallback only
MODEL_URL = (
    "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/"
    "other/home/{dex_id}.png"
)

# Item sprites (potions, stones, master ball, etc.) — same PokeAPI repo.
ITEM_SPRITE_URL = (
    "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/"
    "{slug}.png"
)

REQUEST_TIMEOUT = 4.0


def _cache_path(dex_id: int, style: str, ext: str = "gif") -> Path:
    return ASSETS_DIR / f"{dex_id:04d}_{style}.{ext}"


def _bundled(filename: str) -> Optional[Path]:
    """A read-only seed asset shipped next to the install, if present. Lets
    a sprite-bundled installer work offline even though the writable cache
    (ASSETS_DIR) lives elsewhere. Returns None in dev (same dir) or when the
    file isn't shipped."""
    if BUNDLED_ASSETS_DIR.resolve() == ASSETS_DIR.resolve():
        return None
    p = BUNDLED_ASSETS_DIR / filename
    return p if p.exists() else None


def _try_download(url: str, dest: Path) -> bool:
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200 and resp.content:
            dest.write_bytes(resp.content)
            return True
        log.debug("download %s -> %s", url, resp.status_code)
    except requests.RequestException as exc:
        log.debug("download %s failed: %s", url, exc)
    return False


def _showdown_slug(eng_name: str) -> str:
    """Pokemon Showdown URLs are lowercase, no hyphens / dots / spaces /
    apostrophes (e.g. mr-mime → mrmime, farfetch'd → farfetchd)."""
    return (
        eng_name.lower()
        .replace("-", "")
        .replace(".", "")
        .replace("'", "")
        .replace(" ", "")
        .replace("_", "")
    )


def _resolve_style_key(style: str, is_rare: bool) -> str:
    """Map (user-facing style, rare flag) to the internal style key that
    has its own URL and cache slot."""
    if style == "bw":
        return "bw_shiny" if is_rare else "bw"
    if style == "showdown":
        return "showdown_shiny" if is_rare else "showdown"
    # legacy / direct keys pass through unchanged
    return style


def _url_for(style: str, dex_id: int) -> Optional[str]:
    if style == "bw":
        return BW_URL.format(dex_id=dex_id)
    if style == "bw_shiny":
        return BW_SHINY_URL.format(dex_id=dex_id)
    if style in ("showdown", "showdown_shiny"):
        from .pokemon_names import get_english_name
        eng = get_english_name(dex_id)
        if not eng:
            return None
        slug = _showdown_slug(eng)
        template = SHOWDOWN_URL if style == "showdown" else SHOWDOWN_SHINY_URL
        return template.format(name=slug)
    return None


def get_buddy_sprite(style: str, dex_id: int) -> Optional[Path]:
    """Return path to the requested style's GIF, fetching if needed.
    Returns None on offline + no cache. `style` here is an internal key
    (one of bw / bw_shiny / showdown / showdown_shiny)."""
    cache = _cache_path(dex_id, style, "gif")
    if cache.exists():
        return cache
    bundled = _bundled(f"{dex_id:04d}_{style}.gif")
    if bundled is not None:
        return bundled
    url = _url_for(style, dex_id)
    if url and _try_download(url, cache):
        return cache
    return None


def get_buddy_sprite_with_fallback(style: str, dex_id: int,
                                   is_rare: bool = False) -> Optional[Path]:
    """Try the requested (style, is_rare) combination; fall back to BW if it
    fails (e.g. Showdown name unknown), and to a static PNG if BW is missing
    too. Used by the bag/dex/buddy renderers — the single source of truth for
    'what sprite should this Pokemon use right now'."""
    # Custom (user-registered) pokemon have no remote URLs to try — every
    # `_url_for` call would 404 and burn a 4-second request timeout. That
    # was making the buddy picker freeze for ~12s with 3 customs in party.
    # Just hit the local bw cache and bail.
    from . import custom_pokemon
    if custom_pokemon.is_custom(dex_id):
        # Custom sprites live under data/custom_sprites/ (user state).
        cache = CUSTOM_SPRITES_DIR / f"{dex_id:04d}_bw.gif"
        if cache.exists():
            return cache
        # Fallback for pre-migration installs that still kept it in assets/.
        legacy = _cache_path(dex_id, "bw", "gif")
        if legacy.exists():
            return legacy
        # Last resort: a seed custom shipped with the install.
        return _bundled(f"{dex_id:04d}_bw.gif")

    resolved = _resolve_style_key(style, is_rare)
    p = get_buddy_sprite(resolved, dex_id)
    if p is not None:
        return p
    # Drop the rare variant first — shiny URLs don't exist for every gen.
    if is_rare:
        base = _resolve_style_key(style, False)
        p = get_buddy_sprite(base, dex_id)
        if p is not None:
            return p
    # Cross-style fallback: BW is the most comprehensive set.
    if resolved != "bw":
        p = get_buddy_sprite("bw", dex_id)
        if p is not None:
            return p
    png = _cache_path(dex_id, "pixel", "png")
    if png.exists():
        return png
    if _try_download(PIXEL_PNG_URL.format(dex_id=dex_id), png):
        return png
    return None


def get_model_sprite(dex_id: int) -> Optional[Path]:
    """3D HOME render — used only for the tray icon fallback."""
    png = _cache_path(dex_id, "model", "png")
    if png.exists():
        return png
    return None


# ---- item sprites (potions, stones, master ball, …) ----

def _item_cache_path(slug: str) -> Path:
    return ASSETS_DIR / f"item_{slug}.png"


def get_item_sprite(slug: Optional[str]) -> Optional[Path]:
    """Cached PokeAPI item sprite for the given slug (e.g. 'fire-stone',
    'master-ball'). Returns None on offline + no cache. Items are small
    (~1–3 KB) so callers can fetch on first display without much pain."""
    if not slug:
        return None
    cache = _item_cache_path(slug)
    if cache.exists():
        return cache
    bundled = _bundled(f"item_{slug}.png")
    if bundled is not None:
        return bundled
    url = ITEM_SPRITE_URL.format(slug=slug)
    if _try_download(url, cache):
        return cache
    return None


def prefetch_item_sprites(slugs) -> None:
    """Best-effort bulk prefetch on a background thread. Safe to call at
    startup — each fetch has a 4s timeout so a slow / blocked network
    doesn't stall the app."""
    def worker() -> None:
        for slug in slugs:
            try:
                get_item_sprite(slug)
            except Exception as exc:  # noqa: BLE001
                log.debug("item sprite prefetch %s failed: %s", slug, exc)
    t = threading.Thread(target=worker, daemon=True)
    t.start()


def get_pixel_sprite(dex_id: int) -> Optional[Path]:
    return get_buddy_sprite("bw", dex_id)


def prefetch(dex_id: int, style: str = "bw") -> None:
    get_buddy_sprite(style, dex_id)


# ---- bulk download ----

def _bulk_worker(style: str, dex_ids: Iterable[int],
                 progress_cb, done_cb, stop_event) -> None:
    ids = list(dex_ids)
    ok = 0
    for i, dex_id in enumerate(ids):
        if stop_event.is_set():
            break
        try:
            # Pre-cache both the normal and rare variants for the chosen
            # style so wild encounters and the dex render instantly.
            if get_buddy_sprite(style, dex_id) is not None:
                ok += 1
            rare_key = _resolve_style_key(style, True)
            if rare_key != style:
                get_buddy_sprite(rare_key, dex_id)
        except Exception as exc:  # noqa: BLE001
            log.debug("bulk fetch %d failed: %s", dex_id, exc)
        if progress_cb is not None:
            try:
                progress_cb(i + 1, len(ids))
            except Exception:  # noqa: BLE001
                pass
    if done_cb is not None:
        try:
            done_cb(ok, len(ids))
        except Exception:  # noqa: BLE001
            pass


def start_bulk_download(style: str, dex_ids: Iterable[int],
                        progress_cb=None, done_cb=None) -> threading.Event:
    stop = threading.Event()
    t = threading.Thread(
        target=_bulk_worker,
        args=(style, dex_ids, progress_cb, done_cb, stop),
        daemon=True,
    )
    t.start()
    return stop
