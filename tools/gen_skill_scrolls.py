"""Regenerate the skill teaching-scroll library under ``scrolls/``.

Each file is a ``.scroll`` carrying one skill's identity; importing it banks the
matching teaching scroll in the inventory — see pokemon_transfer.import_file.

Run from anywhere:  python tools/gen_skill_scrolls.py
Covers every skill registered in pokemon_buddy.skills.SKILLS.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `pokemon_buddy` importable when run as a plain script.
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from pokemon_buddy import skills as skills_mod              # noqa: E402
from pokemon_buddy import pokemon_transfer as xfer          # noqa: E402

OUT_DIR = _ROOT / "scrolls"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    made = 0
    for skill in skills_mod.SKILLS.values():
        fname = xfer.suggested_skill_filename(skill.name)
        xfer.build_skill_file(OUT_DIR / fname, skill.item_key)
        made += 1
    print(f"generated {made} skill scrolls in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
