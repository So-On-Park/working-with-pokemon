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
    SKILL = "skill"      # teaching scrolls (두루마리) — 사용 → 파티원에게 기술 전수


@dataclass(frozen=True)
class ItemDef:
    key: str            # storage key, e.g. "food.apple" or "special.fire-stone"
    kind: ItemKind
    emoji: str          # fallback / decorative glyph
    label: str          # Korean display name
    # PokeAPI sprite slug under sprites/items/{slug}.png. Set for SPECIAL
    # items; None means render the emoji glyph instead.
    slug: Optional[str] = None
    # One-line effect summary, surfaced via the ⓘ info icon in the bag UI so
    # the tiles stay uncluttered.
    description: str = ""


# Catalog. Order in each kind controls priority when auto-consuming.
ITEMS: List[ItemDef] = [
    # food
    ItemDef("food.apple",     ItemKind.FOOD,     "🍎", "사과",
            description="밥주기에 쓰는 음식. 주면 친밀도가 조금 올라가."),
    ItemDef("food.berry",     ItemKind.FOOD,     "🍓", "딸기",
            description="밥주기에 쓰는 음식. 주면 친밀도가 조금 올라가."),
    ItemDef("food.cake",      ItemKind.FOOD,     "🍰", "케이크",
            description="밥주기에 쓰는 음식. 주면 친밀도가 조금 올라가."),
    ItemDef("food.cookie",    ItemKind.FOOD,     "🍪", "과자",
            description="밥주기에 쓰는 음식. 주면 친밀도가 조금 올라가."),
    # more foods — meals, veggies, desserts, snacks
    ItemDef("food.pizza",     ItemKind.FOOD,     "🍕", "피자"),
    ItemDef("food.burger",    ItemKind.FOOD,     "🍔", "햄버거"),
    ItemDef("food.fries",     ItemKind.FOOD,     "🍟", "감자튀김"),
    ItemDef("food.hotdog",    ItemKind.FOOD,     "🌭", "핫도그"),
    ItemDef("food.egg",       ItemKind.FOOD,     "🍳", "계란프라이"),
    ItemDef("food.pancake",   ItemKind.FOOD,     "🥞", "팬케이크"),
    ItemDef("food.salad",     ItemKind.FOOD,     "🥗", "샐러드"),
    ItemDef("food.kebab",     ItemKind.FOOD,     "🥙", "케밥"),
    ItemDef("food.steak",     ItemKind.FOOD,     "🥩", "스테이크"),
    ItemDef("food.ramen",     ItemKind.FOOD,     "🍜", "라멘"),
    ItemDef("food.sushi",     ItemKind.FOOD,     "🍣", "초밥"),
    ItemDef("food.fondue",    ItemKind.FOOD,     "🫕", "퐁뒤"),
    ItemDef("food.dango",     ItemKind.FOOD,     "🍡", "경단"),
    ItemDef("food.grapes",    ItemKind.FOOD,     "🍇", "포도"),
    ItemDef("food.chestnut",  ItemKind.FOOD,     "🌰", "군밤"),
    ItemDef("food.pepper",    ItemKind.FOOD,     "🫑", "피망"),
    ItemDef("food.olive",     ItemKind.FOOD,     "🫒", "올리브"),
    ItemDef("food.chili",     ItemKind.FOOD,     "🌶️", "고추"),

    # toys
    ItemDef("toy.ball",       ItemKind.TOY,      "🎾", "공",
            description="놀아주기에 쓰는 장난감. EXP와 친밀도가 올라가."),
    ItemDef("toy.kite",       ItemKind.TOY,      "🪁", "연",
            description="놀아주기에 쓰는 장난감. EXP와 친밀도가 올라가."),
    ItemDef("toy.bell",       ItemKind.TOY,      "🔔", "방울",
            description="놀아주기에 쓰는 장난감. EXP와 친밀도가 올라가."),
    # more toys — balls, instruments, craft, etc.
    ItemDef("toy.firecracker", ItemKind.TOY,     "🧨", "폭죽"),
    ItemDef("toy.palette",    ItemKind.TOY,      "🎨", "팔레트"),
    ItemDef("toy.baseball",   ItemKind.TOY,      "⚾", "야구공"),
    ItemDef("toy.softball",   ItemKind.TOY,      "🥎", "소프트볼"),
    ItemDef("toy.basketball", ItemKind.TOY,      "🏀", "농구공"),
    ItemDef("toy.volleyball", ItemKind.TOY,      "🏐", "배구공"),
    ItemDef("toy.football",   ItemKind.TOY,      "🏈", "미식축구공"),
    ItemDef("toy.soccer",     ItemKind.TOY,      "⚽", "축구공"),
    ItemDef("toy.lipstick",   ItemKind.TOY,      "💄", "립스틱"),
    ItemDef("toy.pingpong",   ItemKind.TOY,      "🏓", "탁구"),
    ItemDef("toy.dice",       ItemKind.TOY,      "🎲", "주사위"),
    ItemDef("toy.teddy",      ItemKind.TOY,      "🧸", "곰인형"),
    ItemDef("toy.wand",       ItemKind.TOY,      "🪄", "요술봉"),
    ItemDef("toy.cards",      ItemKind.TOY,      "🎴", "화투"),
    ItemDef("toy.yoyo",       ItemKind.TOY,      "🪀", "요요"),
    ItemDef("toy.horn",       ItemKind.TOY,      "📯", "나팔"),
    ItemDef("toy.flute",      ItemKind.TOY,      "🪈", "피리"),
    ItemDef("toy.maracas",    ItemKind.TOY,      "🪇", "마라카스"),
    ItemDef("toy.violin",     ItemKind.TOY,      "🎻", "바이올린"),
    ItemDef("toy.piano",      ItemKind.TOY,      "🎹", "피아노"),
    ItemDef("toy.crayon",     ItemKind.TOY,      "🖍️", "크레용"),
    ItemDef("toy.bubble",     ItemKind.TOY,      "🫧", "비눗방울"),

    # pokeballs
    ItemDef("pokeball.basic", ItemKind.POKEBALL, "🔴", "몬스터볼",
            description="야생 포켓몬을 잡을 때 던지는 기본 볼."),

    # special items — rendered with PokeAPI sprites
    ItemDef("special.potion",        ItemKind.SPECIAL, "💊", "상처약",       slug="potion",
            description="사용하면 친밀도 +10."),
    ItemDef("special.super-potion",  ItemKind.SPECIAL, "💊", "고급상처약",   slug="super-potion",
            description="사용하면 친밀도 +25."),
    ItemDef("special.hyper-potion",  ItemKind.SPECIAL, "💊", "초고급상처약", slug="hyper-potion",
            description="사용하면 친밀도 +50."),
    ItemDef("special.rare-candy",    ItemKind.SPECIAL, "🍬", "이상한사탕",   slug="rare-candy",
            description="사용 즉시 EXP +100."),
    ItemDef("special.master-ball",   ItemKind.SPECIAL, "💎", "마스터볼",     slug="master-ball",
            description="장착하면 다음 야생 포켓몬을 무조건 포획."),
    ItemDef("special.fire-stone",    ItemKind.SPECIAL, "🔥", "불꽃의돌",     slug="fire-stone",
            description="맞는 포켓몬(식스테일·가디 등)에게 쓰면 진화해."),
    ItemDef("special.water-stone",   ItemKind.SPECIAL, "💧", "물의돌",       slug="water-stone",
            description="맞는 포켓몬(아쿠스타·셀러 등)에게 쓰면 진화해."),
    ItemDef("special.thunder-stone", ItemKind.SPECIAL, "⚡", "천둥의돌",     slug="thunder-stone",
            description="피카츄·이브이 등에게 쓰면 진화해."),
    ItemDef("special.leaf-stone",    ItemKind.SPECIAL, "🌿", "리프의돌",     slug="leaf-stone",
            description="냄새꼬·우츠동 등에게 쓰면 진화해."),
    ItemDef("special.moon-stone",    ItemKind.SPECIAL, "🌙", "달의돌",       slug="moon-stone",
            description="니드리나·삐삐 등에게 쓰면 진화해."),

    # skill scrolls (두루마리) — teach a technique to a chosen party member.
    ItemDef("skill.collector",       ItemKind.SKILL,   "📜", "수집광 교본",
            description="파티원에게 전수하는 기술 교본. 배운 포켓몬은 화면에 "
                        "떨어진 아이템을 끌어당겨 자동으로 주워와."),
    ItemDef("skill.catcher",         ItemKind.SKILL,   "📜", "명포수 교본",
            description="배운 포켓몬은 야생 포켓몬이 나타나면 자동으로 "
                        "몬스터볼을 던져 잡아줘. (레벨 100이면 스스로 깨우침)"),
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
