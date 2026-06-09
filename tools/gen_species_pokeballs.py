"""Regenerate the shipped species-only .pokeball library under ``pokeballs/``.

Each file is a *species template* (no individual data): importing one creates
a fresh catch (level 1, random basics) — see pokemon_transfer.build_species_file.

Run from anywhere:  python tools/gen_species_pokeballs.py
Covers vanilla dex 1-151 (names from the cached names_ko.json) + every
registered custom pokemon (GIF embedded so recipients can use it offline).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `pokemon_buddy` importable when run as a plain script.
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from pokemon_buddy import custom_pokemon, pokemon_names  # noqa: E402
from pokemon_buddy import pokemon_transfer as xfer       # noqa: E402

OUT_DIR = _ROOT / "pokeballs"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    made = 0

    # Vanilla Gen 1 (offline: cached Korean names only).
    for dex in range(1, 152):
        name = pokemon_names.get_name_cached(dex) or f"#{dex:04d}"
        fname = xfer._sanitize_filename(name) + xfer.POKEMON_EXT
        xfer.build_species_file(OUT_DIR / fname, dex_id=dex, name_ko=name)
        made += 1

    # Registered custom pokemon (GIF embedded).
    for dex in custom_pokemon.list_dex_ids():
        name = custom_pokemon.get_custom_name(dex) or f"#{dex:04d}"
        fname = xfer._sanitize_filename(name) + xfer.POKEMON_EXT
        xfer.build_species_file(OUT_DIR / fname, dex_id=dex, name_ko=name)
        made += 1

    print(f"generated {made} species files in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
