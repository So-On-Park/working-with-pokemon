"""Fill the LOCAL save (data/buddy.db) with broad test content.

Run with the app CLOSED, then start the app:
    python tools/seed_dev_data.py

Tops inventory to max, fills the dex, and adds a spread of bag pokemon (some
knowing 수집광). Alternatively, toggle developer mode in-app (the secret
pokéball tap in 기능 설명) and use the tray action "🧪 테스트 데이터 채우기".
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from pokemon_buddy import dev_seed          # noqa: E402
from pokemon_buddy.state import Store       # noqa: E402


def main() -> int:
    store = Store()
    store.set_meta("onboarded", "1")
    summary = dev_seed.seed_test_data(store)
    store.close()
    print(f"seeded: items={summary['items_maxed']} "
          f"dex={summary['dex_filled']} bag+={summary['bag_added']}")
    print("앱을 (다시) 실행하면 반영돼요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
