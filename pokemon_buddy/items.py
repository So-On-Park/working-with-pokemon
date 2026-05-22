"""Inventory item catalog.

Four kinds:
  - FOOD     : fed to a Pokemon (밥주기). Emoji glyph.
  - TOY      : used to play (놀아주기). Emoji glyph.
  - POKEBALL : spent to catch a wild Pokemon. Custom painted icon.
  - SPECIAL  : misc items with explicit "use" semantics — healing potions,
               rare candy, master ball, evolution stones. Each carries a
               PokeAPI sprite slug so the inventory + drop windows can show
               real game-art icons instead of an emoji fallback.

Each kind has subtype variants for visual variety; gameplay-wise the kind
plus (for SPECIAL) the key is what matters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class ItemKind(str, Enum):
    FOOD = "food"
    TOY = "toy"
    POKEBALL = "pokeball"
    SPECIAL = "special"


@dataclass(frozen=True)
class ItemDef:
    key: str            # storage key, e.g. "food.apple" or "special.fire-stone"
    kind: ItemKind
    emoji: str          # fallback / decorative glyph
    label: str          # Korean display name
    # PokeAPI sprite slug under sprites/items/{slug}.png. Set for SPECIAL
    # items; None means render the emoji glyph instead.
    slug: Optional[str] = None


# Catalog. Order in each kind controls priority when auto-consuming.
ITEMS: List[ItemDef] = [
    # food
    ItemDef("food.apple",     ItemKind.FOOD,     "🍎", "사과"),
    ItemDef("food.berry",     ItemKind.FOOD,     "🍓", "딸기"),
    ItemDef("food.cake",      ItemKind.FOOD,     "🍰", "케이크"),
    ItemDef("food.cookie",    ItemKind.FOOD,     "🍪", "과자"),

    # toys
    ItemDef("toy.ball",       ItemKind.TOY,      "🎾", "공"),
    ItemDef("toy.kite",       ItemKind.TOY,      "🪁", "연"),
    ItemDef("toy.bell",       ItemKind.TOY,      "🔔", "방울"),

    # pokeballs
    ItemDef("pokeball.basic", ItemKind.POKEBALL, "🔴", "몬스터볼"),

    # special items — rendered with PokeAPI sprites
    ItemDef("special.potion",        ItemKind.SPECIAL, "💊", "상처약",       slug="potion"),
    ItemDef("special.super-potion",  ItemKind.SPECIAL, "💊", "고급상처약",   slug="super-potion"),
    ItemDef("special.hyper-potion",  ItemKind.SPECIAL, "💊", "초고급상처약", slug="hyper-potion"),
    ItemDef("special.rare-candy",    ItemKind.SPECIAL, "🍬", "이상한사탕",   slug="rare-candy"),
    ItemDef("special.master-ball",   ItemKind.SPECIAL, "💎", "마스터볼",     slug="master-ball"),
    ItemDef("special.fire-stone",    ItemKind.SPECIAL, "🔥", "불꽃의돌",     slug="fire-stone"),
    ItemDef("special.water-stone",   ItemKind.SPECIAL, "💧", "물의돌",       slug="water-stone"),
    ItemDef("special.thunder-stone", ItemKind.SPECIAL, "⚡", "천둥의돌",     slug="thunder-stone"),
    ItemDef("special.leaf-stone",    ItemKind.SPECIAL, "🌿", "리프의돌",     slug="leaf-stone"),
    ItemDef("special.moon-stone",    ItemKind.SPECIAL, "🌙", "달의돌",       slug="moon-stone"),
]

ITEMS_BY_KEY: Dict[str, ItemDef] = {it.key: it for it in ITEMS}


def items_of(kind: ItemKind) -> List[ItemDef]:
    return [it for it in ITEMS if it.kind == kind]


def find(key: str) -> Optional[ItemDef]:
    return ITEMS_BY_KEY.get(key)


# Drop-rate weighting by kind. SPECIAL kind is uncommon overall, and within
# it master ball is the rarest individual subtype (see SPECIAL_DROP_WEIGHTS).
DROP_WEIGHTS: Dict[ItemKind, int] = {
    ItemKind.FOOD:     50,
    ItemKind.TOY:      27,
    ItemKind.POKEBALL: 13,
    ItemKind.SPECIAL:  10,
}

# Per-item weights within the SPECIAL kind. Items not listed default to 10.
# Tuned so master ball is the prize-tier drop while potions are common.
SPECIAL_DROP_WEIGHTS: Dict[str, int] = {
    "special.potion":        30,
    "special.super-potion":  18,
    "special.hyper-potion":   8,
    "special.rare-candy":     8,
    "special.master-ball":    2,
    "special.fire-stone":     5,
    "special.water-stone":    5,
    "special.thunder-stone":  5,
    "special.leaf-stone":     5,
    "special.moon-stone":     5,
}
