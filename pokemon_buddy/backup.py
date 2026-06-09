"""Save / restore the user's game state.

A backup is a zip archive (any file extension — the format is detected
by the manifest inside) containing:

  data/                       — the SQLite DB (game state, party, dex)
  assets/custom_pokemon.json  — user-registered custom pokemon registry
  assets/display_scale.json   — per-dex display-scale overrides
  assets/<NNNN>_*.gif         — custom-pokemon sprites (4-digit dex IDs
                                 in the user-authored range 9000+)
  pokemon-buddy.manifest      — version + timestamp, also used to detect
                                 whether a chosen file is actually our zip

PokeAPI cache (vanilla dex 0001-1999) is NOT bundled — those can be
re-downloaded on demand and would bloat the backup significantly.

Restore overwrites in place. Caller is responsible for closing the
Store (and any open Qt widgets that hold sprite refs) BEFORE calling
restore_backup() and for restarting the app afterwards."""

from __future__ import annotations

import json
import logging
import re
import shutil
import time
import zipfile
from pathlib import Path
from typing import Optional

from .config import ASSETS_DIR, CUSTOM_SPRITES_DIR, DATA_DIR, ROOT

log = logging.getLogger(__name__)

MANIFEST_NAME = "pokemon-buddy.manifest"
BACKUP_VERSION = "1"

# Files we always pull from ASSETS_DIR if they exist (small JSONs the user
# might lose otherwise).
_ALWAYS_INCLUDE_ASSETS = (
    "custom_pokemon.json",
    "display_scale.json",
    "names_ko.json",
    "names_eng.json",
    "names_info.json",
)

# Sprite filenames matching this regex are user-authored custom pokemon
# (dex 9000+). Vanilla PokeAPI sprites are 4-digit 0001-1999 and are
# excluded — they're cheap to re-download.
_CUSTOM_SPRITE_RE = re.compile(r"^9\d{3}_.+\.gif$")


def _iter_backup_files() -> list[tuple[Path, str]]:
    """Yield (source_path, arcname) pairs that should land in the zip."""
    pairs: list[tuple[Path, str]] = []

    if DATA_DIR.exists():
        for p in DATA_DIR.iterdir():
            if p.is_file():
                pairs.append((p, f"data/{p.name}"))

    # Custom-pokemon sprites now live under data/custom_sprites/ (update-safe
    # user dir). iterdir() above doesn't recurse, so add them explicitly.
    if CUSTOM_SPRITES_DIR.exists():
        for p in CUSTOM_SPRITES_DIR.iterdir():
            if p.is_file():
                pairs.append((p, f"data/custom_sprites/{p.name}"))

    if ASSETS_DIR.exists():
        for name in _ALWAYS_INCLUDE_ASSETS:
            p = ASSETS_DIR / name
            if p.is_file():
                pairs.append((p, f"assets/{name}"))
        for p in ASSETS_DIR.iterdir():
            if p.is_file() and _CUSTOM_SPRITE_RE.match(p.name):
                pairs.append((p, f"assets/{p.name}"))

    return pairs


def create_backup(dest: Path) -> dict:
    """Write a backup zip to `dest`. Returns a summary dict with
    `byte_size`, `file_count`, `created_at`."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    pairs = _iter_backup_files()

    manifest = {
        "version": BACKUP_VERSION,
        "created_at": time.time(),
        "file_count": len(pairs),
        "app": "pokemon-buddy",
    }

    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for src, arcname in pairs:
            zf.write(src, arcname=arcname)
        zf.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2))

    byte_size = dest.stat().st_size
    log.info("backup created: %s (%d files, %d bytes)",
             dest, len(pairs), byte_size)
    return {
        "byte_size": byte_size,
        "file_count": len(pairs),
        "created_at": manifest["created_at"],
    }


def inspect_backup(src: Path) -> Optional[dict]:
    """Return the manifest dict from a backup zip, or None if the file
    isn't a valid backup. Used to preview before clobbering data."""
    try:
        with zipfile.ZipFile(src, "r") as zf:
            if MANIFEST_NAME not in zf.namelist():
                return None
            data = zf.read(MANIFEST_NAME).decode("utf-8")
            return json.loads(data)
    except (zipfile.BadZipFile, json.JSONDecodeError, OSError) as exc:
        log.debug("inspect_backup failed for %s: %s", src, exc)
        return None


def restore_backup(src: Path) -> dict:
    """Overwrite the user's data/ and assets/ from a backup zip.
    Raises ValueError on validation failure. Returns the manifest dict
    on success."""
    src = Path(src)
    manifest = inspect_backup(src)
    if manifest is None:
        raise ValueError("백업 파일이 아닌 것 같아 (manifest 없음)")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    restored = 0
    with zipfile.ZipFile(src, "r") as zf:
        for name in zf.namelist():
            if name == MANIFEST_NAME:
                continue
            # zip-slip defense — checked BEFORE the prefix filter so a
            # malicious archive can't smuggle '..' past us by claiming
            # to be in an unknown directory.
            parts = name.replace("\\", "/").split("/")
            if any(p == ".." for p in parts) or name.startswith("/"):
                raise ValueError(f"안전하지 않은 경로: {name}")
            # Route by prefix into the live data/assets dirs. The zip's
            # path layout is informational — we don't trust it for the
            # destination directory.
            if name.startswith("data/"):
                target = DATA_DIR / name[len("data/"):]
            elif name.startswith("assets/"):
                target = ASSETS_DIR / name[len("assets/"):]
            else:
                # Unknown prefix — ignore quietly so future format
                # additions don't break old restorers.
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(name) as src_f, open(target, "wb") as dst_f:
                shutil.copyfileobj(src_f, dst_f)
            restored += 1

    log.info("backup restored: %s (%d files)", src, restored)
    return manifest
