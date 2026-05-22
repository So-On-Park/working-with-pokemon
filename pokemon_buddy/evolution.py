"""Pokemon evolution data and lookups (Gen 1 only).

Each entry maps a dex_id to (next_form_dex_id, min_level). Some Gen 1
evolutions canonically use stones, trades, or friendship; we collapse all
of those into a level threshold so the game stays self-contained."""

from __future__ import annotations

from typing import Optional, Tuple


# base_dex_id -> (next_dex_id, min_level)
GEN1_EVOLUTIONS: dict[int, Tuple[int, int]] = {
    1: (2, 16),    2: (3, 32),       # Bulbasaur → Ivysaur → Venusaur
    4: (5, 16),    5: (6, 36),       # Charmander → Charmeleon → Charizard
    7: (8, 16),    8: (9, 36),       # Squirtle → Wartortle → Blastoise
    10: (11, 7),   11: (12, 10),     # Caterpie → Metapod → Butterfree
    13: (14, 7),   14: (15, 10),     # Weedle → Kakuna → Beedrill
    16: (17, 18),  17: (18, 36),     # Pidgey line
    19: (20, 20),                    # Rattata → Raticate
    21: (22, 20),                    # Spearow → Fearow
    23: (24, 22),                    # Ekans → Arbok
    25: (26, 22),                    # Pikachu → Raichu (stone in canon)
    27: (28, 22),                    # Sandshrew → Sandslash
    29: (30, 16),  30: (31, 36),     # Nidoran♀ line (stone in canon)
    32: (33, 16),  33: (34, 36),     # Nidoran♂ line (stone in canon)
    35: (36, 25),                    # Clefairy → Clefable (stone)
    37: (38, 32),                    # Vulpix → Ninetales (stone)
    39: (40, 25),                    # Jigglypuff → Wigglytuff (stone)
    41: (42, 22),                    # Zubat → Golbat
    43: (44, 21),  44: (45, 32),     # Oddish → Gloom → Vileplume
    46: (47, 24),                    # Paras → Parasect
    48: (49, 31),                    # Venonat → Venomoth
    50: (51, 26),                    # Diglett → Dugtrio
    52: (53, 28),                    # Meowth → Persian
    54: (55, 33),                    # Psyduck → Golduck
    56: (57, 28),                    # Mankey → Primeape
    58: (59, 25),                    # Growlithe → Arcanine (stone)
    60: (61, 25),  61: (62, 32),     # Poliwag → Poliwhirl → Poliwrath
    63: (64, 16),  64: (65, 35),     # Abra → Kadabra → Alakazam (trade)
    66: (67, 28),  67: (68, 35),     # Machop → Machoke → Machamp (trade)
    69: (70, 21),  70: (71, 32),     # Bellsprout → Weepinbell → Victreebel
    72: (73, 30),                    # Tentacool → Tentacruel
    74: (75, 25),  75: (76, 35),     # Geodude → Graveler → Golem (trade)
    77: (78, 40),                    # Ponyta → Rapidash
    79: (80, 37),                    # Slowpoke → Slowbro
    81: (82, 30),                    # Magnemite → Magneton
    84: (85, 31),                    # Doduo → Dodrio
    86: (87, 34),                    # Seel → Dewgong
    88: (89, 38),                    # Grimer → Muk
    90: (91, 32),                    # Shellder → Cloyster (stone)
    92: (93, 25),  93: (94, 35),     # Gastly → Haunter → Gengar (trade)
    96: (97, 26),                    # Drowzee → Hypno
    98: (99, 28),                    # Krabby → Kingler
    100: (101, 30),                  # Voltorb → Electrode
    102: (103, 35),                  # Exeggcute → Exeggutor (stone)
    104: (105, 28),                  # Cubone → Marowak
    111: (112, 42),                  # Rhyhorn → Rhydon
    116: (117, 32),                  # Horsea → Seadra
    118: (119, 33),                  # Goldeen → Seaking
    120: (121, 25),                  # Staryu → Starmie (stone)
    129: (130, 20),                  # Magikarp → Gyarados
    133: (134, 25),                  # Eevee → Vaporeon (one of many; simplified)
    138: (139, 40),                  # Omanyte → Omastar
    140: (141, 40),                  # Kabuto → Kabutops
    147: (148, 30),                  # Dratini → Dragonair
    148: (149, 55),                  # Dragonair → Dragonite
}


def get_evolution_target(dex_id: int) -> Optional[Tuple[int, int]]:
    """Return (next_dex_id, min_level) for this Pokemon, or None if it
    doesn't evolve (or is a final form / outside Gen 1)."""
    return GEN1_EVOLUTIONS.get(dex_id)


def can_evolve(dex_id: int, level: int) -> Optional[int]:
    """Return next_dex_id if this Pokemon can evolve at the given level,
    else None. Used right after a level-up to decide whether to prompt."""
    info = GEN1_EVOLUTIONS.get(dex_id)
    if info is None:
        return None
    next_dex, min_level = info
    if level >= min_level:
        return next_dex
    return None


# Stone evolutions (Gen 1). Each entry is `{base_dex_id: evolved_dex_id}`.
# Using the stone on a compatible Pokemon evolves it regardless of level —
# matching canon, where stones bypass the level requirement entirely.
STONE_EVOLUTIONS: dict[str, dict[int, int]] = {
    "fire-stone":    {37: 38,   58: 59,   133: 136},   # Vulpix→Ninetales, Growlithe→Arcanine, Eevee→Flareon
    "water-stone":   {61: 62,   90: 91,   120: 121, 133: 134},   # Poliwhirl→Poliwrath, Shellder→Cloyster, Staryu→Starmie, Eevee→Vaporeon
    "thunder-stone": {25: 26,   133: 135},              # Pikachu→Raichu, Eevee→Jolteon
    "leaf-stone":    {44: 45,   70: 71,   102: 103},    # Gloom→Vileplume, Weepinbell→Victreebel, Exeggcute→Exeggutor
    "moon-stone":    {30: 31,   33: 34,   35: 36,  39: 40},      # Nidorina→Nidoqueen, Nidorino→Nidoking, Clefairy→Clefable, Jigglypuff→Wigglytuff
}


def get_stone_evolution_target(dex_id: int,
                               stone_slug: str) -> Optional[int]:
    """Return the dex_id this Pokemon evolves into when given the named
    stone, or None if it doesn't react to that stone. Used by the item-use
    handler to decide whether the stone has any effect."""
    return STONE_EVOLUTIONS.get(stone_slug, {}).get(dex_id)
