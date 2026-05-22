"""Persistent state.

Conceptual split:
  - `dex`  = species-level registry. Composite key (dex_id, is_rare) so the
             rare variant of a species is its own entry. Carries
             `count`, `first_caught_at`, `last_caught_at`. No stats.
  - `bag`  = the Pokemon you currently own as discrete individuals. One row
             per creature (auto-id), with its own nickname + level + exp +
             friendship + is_rare. Multiple bag entries can share a dex_id.
  - The active buddy is the bag row pointed at by `meta.active_bag_id`.
  - Evolving an individual changes its `bag.dex_id` in place (same creature,
     new form). `is_rare` carries over — a rare Pikachu evolves to a rare
     Raichu. The pre-evolution species stays in `dex` because you've owned
     one before."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from typing import List, Optional

from .config import (
    DB_PATH,
    FRIENDSHIP_DEFAULT,
    RARE_NAME_PREFIX,
    STARTER_DEX_ID,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    message TEXT NOT NULL,
    interval_min INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    last_fired_at REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS dex (
    dex_id INTEGER NOT NULL,
    is_rare INTEGER NOT NULL DEFAULT 0,
    name TEXT NOT NULL,
    first_caught_at REAL NOT NULL,
    last_caught_at REAL NOT NULL,
    count INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (dex_id, is_rare)
);

CREATE TABLE IF NOT EXISTS bag (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dex_id INTEGER NOT NULL,
    is_rare INTEGER NOT NULL DEFAULT 0,
    nickname TEXT,
    nickname_history TEXT NOT NULL DEFAULT '[]',
    level INTEGER NOT NULL DEFAULT 1,
    exp INTEGER NOT NULL DEFAULT 0,
    friendship INTEGER NOT NULL DEFAULT 0,
    friendship_xp INTEGER NOT NULL DEFAULT 0,
    caught_with TEXT NOT NULL DEFAULT 'pokeball.basic',
    personality TEXT NOT NULL DEFAULT 'playful',
    last_interaction_at REAL NOT NULL DEFAULT 0,
    caught_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory (
    item_key TEXT PRIMARY KEY,
    count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS daily_events (
    key TEXT PRIMARY KEY,
    hour INTEGER NOT NULL,
    minute INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    label TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL DEFAULT ''
);

-- Legacy table — kept so we can migrate ancient installs.
CREATE TABLE IF NOT EXISTS buddy (
    id INTEGER PRIMARY KEY,
    dex_id INTEGER NOT NULL,
    nickname TEXT,
    level INTEGER NOT NULL DEFAULT 1,
    exp INTEGER NOT NULL DEFAULT 0,
    hunger INTEGER NOT NULL DEFAULT 20,
    happiness INTEGER NOT NULL DEFAULT 80,
    last_tick REAL NOT NULL,
    caught_at REAL NOT NULL
);
"""

DEFAULT_REMINDERS = [
    ("물 마시기",   "물 한 잔 마실 시간이야! 💧", 40),
    ("스트레칭",   "잠깐 일어나서 스트레칭 하자! 🤸", 60),
    ("눈 휴식",    "20초 동안 먼 곳을 봐줘 👀 (20-20-20 규칙)", 20),
    ("자세 체크",  "허리 펴기! 자세 점검 시간이야 🪑", 45),
]


@dataclass
class DexEntry:
    dex_id: int
    is_rare: bool
    name: str                # base species name (no "레어" prefix)
    first_caught_at: float
    last_caught_at: float
    count: int

    @property
    def display_name(self) -> str:
        return f"{RARE_NAME_PREFIX} {self.name}" if self.is_rare else self.name


@dataclass
class DailyEvent:
    """One wall-clock alarm. Two flavors:

    - Built-in (`is_builtin=True`, key ∈ {morning, lunch, farewell}): the
      label is fixed (출근 인사 etc.) and `message` is empty — the
      schedule engine pulls a personality-flavored line from messages.py
      each time it fires.
    - Custom (any other key): the user picks a label + a literal message
      text. The engine emits that exact text. Deletable in the UI."""
    key: str
    label: str
    hour: int
    minute: int
    enabled: bool
    message: str
    is_builtin: bool


# Display names + display order for the three fixed schedule events. The
# message banks in messages.py are keyed off these same `key` strings.
DAILY_EVENT_LABELS = {
    "morning":  "출근 인사",
    "lunch":    "점심 알람",
    "farewell": "퇴근 인사",
}
DAILY_EVENT_ORDER = ["morning", "lunch", "farewell"]
BUILTIN_EVENT_KEYS = set(DAILY_EVENT_ORDER)


@dataclass
class Reminder:
    id: Optional[int]
    name: str
    message: str
    interval_min: int
    enabled: bool
    last_fired_at: float

    def is_due(self, now: float) -> bool:
        if not self.enabled:
            return False
        return (now - self.last_fired_at) >= self.interval_min * 60


@dataclass
class Buddy:
    """One creature in the bag. `bag_id` is the per-individual identifier;
    `dex_id` is its species. The Buddy dataclass IS a bag row."""
    bag_id: int
    dex_id: int
    is_rare: bool
    name: str                    # base species name (e.g. "피카츄")
    nickname: Optional[str]
    level: int
    exp: int
    friendship: int              # 0..100 — the only relationship stat now
    friendship_xp: int           # 0..FRIENDSHIP_XP_PER_POINT-1, hidden progress
    caught_with: str             # item key of the ball used to catch it
    personality: str             # Personality enum value (e.g. 'playful')
    nickname_history: str        # JSON list of {nickname, set_at} entries
    last_interaction_at: float
    caught_at: float

    @property
    def exp_to_next(self) -> int:
        return self.level * 100

    @property
    def species_label(self) -> str:
        """Species name with the rare prefix when applicable. Used when we
        need to refer to the kind of Pokemon, ignoring nicknames."""
        return f"{RARE_NAME_PREFIX} {self.name}" if self.is_rare else self.name

    @property
    def display_name(self) -> str:
        """What the user actually sees as this individual's name. A custom
        nickname overrides everything; otherwise we use the species label
        (which already accounts for rare)."""
        if self.nickname:
            return self.nickname
        return self.species_label

    @property
    def mood(self) -> str:
        if self.friendship >= 70:
            return "happy"
        if self.friendship <= 20:
            return "sad"
        return "ok"

    @property
    def hearts(self) -> int:
        return max(0, min(5, self.friendship // 20))


def _clamp(v: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, v))


# Stat columns the pre-bag schema added to `dex`. The legacy migration leaves
# them in place but the current code never reads them.
_LEGACY_DEX_STAT_COLUMNS = [
    "nickname", "level", "exp", "hunger", "happiness", "friendship",
    "last_tick", "last_interaction_at",
]


class Store:
    def __init__(self) -> None:
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        # Migrations run in order — every prior version ends up with the
        # current bag+dex shape.
        self._migrate_legacy_buddy_to_dex()
        self._migrate_dex_stats_to_bag()
        self._migrate_drop_hunger_add_rare()
        self._migrate_dex_add_rare()
        self._migrate_add_friendship_xp_caught_with()
        self._migrate_add_personality()
        self._migrate_add_nickname_history()
        self._migrate_reset_legacy_default_friendship()
        self._migrate_add_alarm_label_message()
        self._ensure_active_buddy()
        self._ensure_default_reminders()
        self._ensure_starter_items()
        self._ensure_default_schedule_events()

    # ---------- meta ----------
    def get_meta(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO meta(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.conn.commit()

    # ---------- migrations ----------
    def _table_columns(self, table: str) -> set:
        return {r["name"] for r in
                self.conn.execute(f"PRAGMA table_info({table})").fetchall()}

    def _dex_has_stat_columns(self) -> bool:
        return "level" in self._table_columns("dex")

    def _migrate_legacy_buddy_to_dex(self) -> None:
        """Old `buddy` table → stats embedded in `dex`. Idempotent."""
        if self.get_meta("buddy_migrated") == "1":
            return
        cols = self._table_columns("dex")
        adds = [
            ("nickname",            "TEXT"),
            ("level",               "INTEGER NOT NULL DEFAULT 1"),
            ("exp",                 "INTEGER NOT NULL DEFAULT 0"),
            ("hunger",              "INTEGER NOT NULL DEFAULT 20"),
            ("happiness",           "INTEGER NOT NULL DEFAULT 80"),
            ("friendship",          f"INTEGER NOT NULL DEFAULT {FRIENDSHIP_DEFAULT}"),
            ("last_tick",           "REAL NOT NULL DEFAULT 0"),
            ("last_interaction_at", "REAL NOT NULL DEFAULT 0"),
        ]
        for name, defn in adds:
            if name not in cols:
                self.conn.execute(f"ALTER TABLE dex ADD COLUMN {name} {defn}")
        row = self.conn.execute("SELECT * FROM buddy LIMIT 1").fetchone()
        if row is not None:
            now = time.time()
            self.conn.execute(
                "INSERT OR IGNORE INTO dex(dex_id, name, first_caught_at, "
                "last_caught_at, count) VALUES(?,?,?,?,1)",
                (row["dex_id"], f"#{row['dex_id']:04d}",
                 row["caught_at"], row["caught_at"]),
            )
            self.conn.execute(
                "UPDATE dex SET nickname=?, level=?, exp=?, hunger=?, "
                "happiness=?, last_tick=?, last_interaction_at=? "
                "WHERE dex_id=?",
                (row["nickname"], row["level"], row["exp"], row["hunger"],
                 row["happiness"], row["last_tick"], now, row["dex_id"]),
            )
            self.set_meta("active_dex_id", str(row["dex_id"]))
        self.set_meta("buddy_migrated", "1")
        self.conn.commit()

    def _migrate_dex_stats_to_bag(self) -> None:
        """dex-with-stats → split into species `dex` + per-individual `bag`."""
        if self.get_meta("bag_migrated") == "1":
            return
        if not self._dex_has_stat_columns():
            self.set_meta("bag_migrated", "1")
            return

        existing_bag = self.conn.execute("SELECT COUNT(*) AS c FROM bag").fetchone()
        if existing_bag and existing_bag["c"] > 0:
            self.set_meta("bag_migrated", "1")
            return

        active_dex_str = self.get_meta("active_dex_id")
        try:
            active_dex_id = int(active_dex_str) if active_dex_str else None
        except ValueError:
            active_dex_id = None
        active_bag_id: Optional[int] = None

        # The bag table at this point may still have the legacy schema (with
        # hunger/happiness/last_tick) if it was created during the previous
        # version's migration. We populate every legacy column we know about
        # so the INSERT works regardless; the next migration strips them.
        bag_cols = self._table_columns("bag")
        rows = self.conn.execute("SELECT * FROM dex").fetchall()
        for r in rows:
            if "hunger" in bag_cols:
                cur = self.conn.execute(
                    "INSERT INTO bag(dex_id, nickname, level, exp, hunger, "
                    "happiness, friendship, last_tick, last_interaction_at, "
                    "caught_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (r["dex_id"], r["nickname"], r["level"], r["exp"],
                     r["hunger"], r["happiness"], r["friendship"],
                     r["last_tick"], r["last_interaction_at"],
                     r["first_caught_at"]),
                )
            else:
                cur = self.conn.execute(
                    "INSERT INTO bag(dex_id, nickname, level, exp, friendship, "
                    "last_interaction_at, caught_at) VALUES(?,?,?,?,?,?,?)",
                    (r["dex_id"], r["nickname"], r["level"], r["exp"],
                     r["friendship"], r["last_interaction_at"],
                     r["first_caught_at"]),
                )
            if active_dex_id is not None and r["dex_id"] == active_dex_id:
                active_bag_id = cur.lastrowid

        if active_bag_id is not None:
            self.set_meta("active_bag_id", str(active_bag_id))
        self.set_meta("bag_migrated", "1")
        self.conn.commit()

    def _migrate_drop_hunger_add_rare(self) -> None:
        """Rebuild `bag` to drop hunger/happiness/last_tick and add is_rare.
        SQLite < 3.35 can't DROP COLUMN, so we copy into a fresh table."""
        if self.get_meta("bag_v2_migrated") == "1":
            return
        cols = self._table_columns("bag")
        needs_rebuild = ("hunger" in cols) or ("happiness" in cols) or \
                        ("last_tick" in cols) or ("is_rare" not in cols)
        if not needs_rebuild:
            self.set_meta("bag_v2_migrated", "1")
            return

        self.conn.execute("""
            CREATE TABLE bag_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dex_id INTEGER NOT NULL,
                is_rare INTEGER NOT NULL DEFAULT 0,
                nickname TEXT,
                level INTEGER NOT NULL DEFAULT 1,
                exp INTEGER NOT NULL DEFAULT 0,
                friendship INTEGER NOT NULL DEFAULT 30,
                last_interaction_at REAL NOT NULL DEFAULT 0,
                caught_at REAL NOT NULL
            )
        """)
        is_rare_expr = "is_rare" if "is_rare" in cols else "0"
        last_int_expr = ("last_interaction_at" if "last_interaction_at" in cols
                         else "caught_at")
        friendship_expr = ("friendship" if "friendship" in cols
                           else str(FRIENDSHIP_DEFAULT))
        self.conn.execute(f"""
            INSERT INTO bag_v2 (id, dex_id, is_rare, nickname, level, exp,
                                friendship, last_interaction_at, caught_at)
            SELECT id, dex_id, {is_rare_expr}, nickname, level, exp,
                   {friendship_expr}, {last_int_expr}, caught_at
            FROM bag
        """)
        self.conn.execute("DROP TABLE bag")
        self.conn.execute("ALTER TABLE bag_v2 RENAME TO bag")
        self.set_meta("bag_v2_migrated", "1")
        self.conn.commit()

    def _migrate_add_alarm_label_message(self) -> None:
        """daily_events v2: add `label` + `message` columns so the user can
        author custom alarms with their own text alongside the three
        personality-flavored built-ins."""
        if self.get_meta("daily_events_v2_migrated") == "1":
            return
        cols = self._table_columns("daily_events")
        if "label" not in cols:
            self.conn.execute(
                "ALTER TABLE daily_events ADD COLUMN label TEXT NOT NULL DEFAULT ''"
            )
        if "message" not in cols:
            self.conn.execute(
                "ALTER TABLE daily_events ADD COLUMN message TEXT NOT NULL DEFAULT ''"
            )
        # Backfill labels for the built-ins so the UI has something to show.
        for key, label in DAILY_EVENT_LABELS.items():
            self.conn.execute(
                "UPDATE daily_events SET label=? WHERE key=? AND label=''",
                (label, key),
            )
        self.set_meta("daily_events_v2_migrated", "1")
        self.conn.commit()

    def _migrate_reset_legacy_default_friendship(self) -> None:
        """One-shot fix for installs where new catches landed at friendship
        30 because the bag table was originally created with that as the
        SQL DEFAULT (back when FRIENDSHIP_DEFAULT was 30). Entries that
        look like bug victims — exactly fr=30, zero xp, no nickname, no
        idle-decay activity yet — get reset to fr=0.

        Bona-fide grinded entries are safe: they almost always have either
        a non-30 friendship value, some xp accumulated, or a nickname set
        — at least one of those, so the WHERE clause skips them."""
        if self.get_meta("legacy_fr30_cleaned") == "1":
            return
        cur = self.conn.execute(
            "UPDATE bag SET friendship=0, friendship_xp=0 "
            "WHERE friendship=30 AND friendship_xp=0 AND nickname IS NULL"
        )
        if cur.rowcount > 0:
            import logging as _lg
            _lg.getLogger(__name__).info(
                "reset %d bag entries from legacy fr=30 default → 0",
                cur.rowcount,
            )
        self.set_meta("legacy_fr30_cleaned", "1")
        self.conn.commit()

    def _migrate_add_nickname_history(self) -> None:
        """Bag v5: nickname change log. JSON array of {nickname, set_at}
        entries — append on every rename, plus a seed entry for the current
        nickname so existing buddies have at least one history row."""
        if self.get_meta("bag_v5_migrated") == "1":
            return
        cols = self._table_columns("bag")
        if "nickname_history" not in cols:
            self.conn.execute(
                "ALTER TABLE bag ADD COLUMN nickname_history "
                "TEXT NOT NULL DEFAULT '[]'"
            )
        # Seed: if a buddy has a nickname but no history yet, log it as the
        # earliest entry (set_at = caught_at — best guess).
        import json as _j
        rows = self.conn.execute(
            "SELECT id, nickname, caught_at, nickname_history FROM bag"
        ).fetchall()
        for row in rows:
            current_hist = row["nickname_history"] or "[]"
            try:
                existing = _j.loads(current_hist)
            except ValueError:
                existing = []
            if existing or not row["nickname"]:
                continue
            existing.append({
                "nickname": row["nickname"],
                "set_at": row["caught_at"],
            })
            self.conn.execute(
                "UPDATE bag SET nickname_history=? WHERE id=?",
                (_j.dumps(existing, ensure_ascii=False), row["id"]),
            )
        self.set_meta("bag_v5_migrated", "1")
        self.conn.commit()

    def _migrate_add_personality(self) -> None:
        """Bag v4: each individual carries a personality string. Existing
        rows get a random personality assigned once (so the user's grandfathered
        Pokemon aren't all the same flavor)."""
        if self.get_meta("bag_v4_migrated") == "1":
            return
        cols = self._table_columns("bag")
        if "personality" not in cols:
            self.conn.execute(
                "ALTER TABLE bag ADD COLUMN personality "
                "TEXT NOT NULL DEFAULT 'playful'"
            )
        # One-time randomization for any existing rows.
        import random as _r
        choices = ["playful", "calm", "brave", "shy", "naive", "smart"]
        rows = self.conn.execute("SELECT id FROM bag").fetchall()
        for row in rows:
            self.conn.execute(
                "UPDATE bag SET personality=? WHERE id=?",
                (_r.choice(choices), row["id"]),
            )
        self.set_meta("bag_v4_migrated", "1")
        self.conn.commit()

    def _migrate_add_friendship_xp_caught_with(self) -> None:
        """Bag v3: add the hidden XP accumulator for slow friendship growth
        plus a `caught_with` column so each individual remembers which ball
        was used to catch it. Both default to safe values for existing rows
        (xp=0, caught_with='pokeball.basic')."""
        if self.get_meta("bag_v3_migrated") == "1":
            return
        cols = self._table_columns("bag")
        if "friendship_xp" not in cols:
            self.conn.execute(
                "ALTER TABLE bag ADD COLUMN friendship_xp "
                "INTEGER NOT NULL DEFAULT 0"
            )
        if "caught_with" not in cols:
            self.conn.execute(
                "ALTER TABLE bag ADD COLUMN caught_with "
                "TEXT NOT NULL DEFAULT 'pokeball.basic'"
            )
        self.set_meta("bag_v3_migrated", "1")
        self.conn.commit()

    def _migrate_dex_add_rare(self) -> None:
        """Rebuild `dex` so the primary key is (dex_id, is_rare), letting the
        rare variant of a species coexist with the normal entry."""
        if self.get_meta("dex_v2_migrated") == "1":
            return
        cols = self._table_columns("dex")
        if "is_rare" in cols:
            self.set_meta("dex_v2_migrated", "1")
            return

        self.conn.execute("""
            CREATE TABLE dex_v2 (
                dex_id INTEGER NOT NULL,
                is_rare INTEGER NOT NULL DEFAULT 0,
                name TEXT NOT NULL,
                first_caught_at REAL NOT NULL,
                last_caught_at REAL NOT NULL,
                count INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (dex_id, is_rare)
            )
        """)
        self.conn.execute("""
            INSERT INTO dex_v2 (dex_id, is_rare, name, first_caught_at,
                                last_caught_at, count)
            SELECT dex_id, 0, name, first_caught_at, last_caught_at, count
            FROM dex
        """)
        self.conn.execute("DROP TABLE dex")
        self.conn.execute("ALTER TABLE dex_v2 RENAME TO dex")
        self.set_meta("dex_v2_migrated", "1")
        self.conn.commit()

    def _ensure_active_buddy(self) -> None:
        """Make sure the bag has at least one entry and active_bag_id points
        at a real row. On a fresh install, seed the starter."""
        active_str = self.get_meta("active_bag_id")
        if active_str:
            try:
                bag_id = int(active_str)
            except ValueError:
                bag_id = None
            if bag_id is not None:
                row = self.conn.execute("SELECT id FROM bag WHERE id=?",
                                        (bag_id,)).fetchone()
                if row:
                    return

        first = self.conn.execute(
            "SELECT id FROM bag ORDER BY id LIMIT 1"
        ).fetchone()
        if first is not None:
            self.set_meta("active_bag_id", str(first["id"]))
            return

        # Bag is empty. Defer seeding to BuddyApp's onboarding flow — the
        # user picks their starter from a pokéball selection. We only fall
        # back to the hard-coded STARTER_DEX_ID if onboarding already ran
        # but somehow nothing got persisted (corruption, manual deletion).
        if not self.get_meta("onboarded"):
            return

        now = time.time()
        self.conn.execute(
            "INSERT OR IGNORE INTO dex(dex_id, is_rare, name, first_caught_at, "
            "last_caught_at, count) VALUES(?,0,?,?,?,1)",
            (STARTER_DEX_ID, f"#{STARTER_DEX_ID:04d}", now, now),
        )
        import random as _r
        starter_personality = _r.choice(
            ["playful", "calm", "brave", "shy", "naive", "smart"]
        )
        cur = self.conn.execute(
            "INSERT INTO bag(dex_id, is_rare, level, exp, friendship, "
            "friendship_xp, personality, nickname_history, "
            "last_interaction_at, caught_at) "
            "VALUES(?,0,1,0,0,0,?,'[]',?,?)",
            (STARTER_DEX_ID, starter_personality, now, now),
        )
        self.set_meta("active_bag_id", str(cur.lastrowid))
        self.conn.commit()

    # ---------- species name resolution ----------
    def _species_name(self, dex_id: int) -> str:
        """Return the resolved Korean (or English) species name for `dex_id`.
        Bag entries only carry `dex_id`, so we hop through the dex registry
        first; if that still has a placeholder, fall back to the names cache
        and self-heal the dex row so future lookups are cheap."""
        # Normal-form row carries the canonical name. (Rare and normal share
        # the same species name string; rare is just a presentation flag.)
        row = self.conn.execute(
            "SELECT name FROM dex WHERE dex_id=? ORDER BY is_rare LIMIT 1",
            (dex_id,),
        ).fetchone()
        if row and row["name"] and not row["name"].startswith("#"):
            return row["name"]

        # Dex name not resolved yet — try the offline names cache so the bag
        # UI doesn't show "#0025" for a Pikachu we already know about.
        from .pokemon_names import get_name_cached, fallback_name
        cached = get_name_cached(dex_id)
        if cached:
            self.conn.execute(
                "UPDATE dex SET name=? WHERE dex_id=? AND "
                "(name IS NULL OR name='' OR name LIKE '#%')",
                (cached, dex_id),
            )
            self.conn.commit()
            return cached
        return fallback_name(dex_id)

    def set_species_name(self, dex_id: int, name: str) -> None:
        """Persist the resolved species name across every dex row for this
        species (both normal and rare share the same base name)."""
        self.conn.execute("UPDATE dex SET name=? WHERE dex_id=?",
                          (name, dex_id))
        self.conn.commit()

    # ---------- buddy (active bag entry) ----------
    def _row_to_buddy(self, row: sqlite3.Row) -> Buddy:
        return Buddy(
            bag_id=row["id"],
            dex_id=row["dex_id"],
            is_rare=bool(row["is_rare"]),
            name=self._species_name(row["dex_id"]),
            nickname=row["nickname"],
            level=row["level"],
            exp=row["exp"],
            friendship=row["friendship"],
            friendship_xp=row["friendship_xp"],
            caught_with=row["caught_with"],
            personality=row["personality"],
            nickname_history=row["nickname_history"] or "[]",
            last_interaction_at=row["last_interaction_at"],
            caught_at=row["caught_at"],
        )

    def load_active_buddy(self) -> Buddy:
        bag_str = self.get_meta("active_bag_id")
        try:
            bag_id = int(bag_str) if bag_str else None
        except ValueError:
            bag_id = None
        row = None
        if bag_id is not None:
            row = self.conn.execute("SELECT * FROM bag WHERE id=?",
                                    (bag_id,)).fetchone()
        if row is None:
            row = self.conn.execute(
                "SELECT * FROM bag ORDER BY id LIMIT 1"
            ).fetchone()
            if row is None:
                self._ensure_active_buddy()
                row = self.conn.execute(
                    "SELECT * FROM bag ORDER BY id LIMIT 1"
                ).fetchone()
        return self._row_to_buddy(row)

    def save_active_buddy(self, b: Buddy) -> None:
        self.conn.execute(
            "UPDATE bag SET dex_id=?, is_rare=?, nickname=?, level=?, exp=?, "
            "friendship=?, friendship_xp=?, last_interaction_at=? "
            "WHERE id=?",
            (b.dex_id, int(b.is_rare), b.nickname, b.level, b.exp,
             b.friendship, b.friendship_xp, b.last_interaction_at, b.bag_id),
        )
        self.conn.commit()

    def swap_active_buddy(self, bag_id: int) -> None:
        # Caller guarantees bag_id exists. Also keeps the party JSON in
        # sync — the swapped-in buddy becomes the new primary (slot 0).
        # If that bag_id wasn't in the party, replace slot 0 with it.
        self.set_meta("active_bag_id", str(bag_id))
        party = self.load_active_party()
        if not party:
            party = [bag_id]
        elif bag_id in party:
            party = [bag_id] + [b for b in party if b != bag_id]
        else:
            party = [bag_id] + party[1:]   # bump out current primary
        self.save_active_party(party)

    # ---------- party (up to 3 simultaneous buddies) ----------
    PARTY_MAX = 3

    def load_active_party(self) -> List[int]:
        """Current party as a list of bag_ids in slot order. Bootstraps
        from the legacy singular `active_bag_id` for DBs that predate the
        party feature."""
        import json as _json
        raw = self.get_meta("active_party")
        if raw:
            try:
                ids = _json.loads(raw)
                if isinstance(ids, list) and ids:
                    return [int(i) for i in ids]
            except (ValueError, TypeError):
                pass
        single = self.get_meta("active_bag_id")
        if single:
            try:
                return [int(single)]
            except ValueError:
                pass
        return []

    def save_active_party(self, bag_ids: List[int]) -> None:
        """Persist the party JSON + mirror primary into `active_bag_id`
        for any code path that still reads the singular pointer."""
        if not bag_ids:
            raise ValueError("party cannot be empty")
        import json as _json
        clean = [int(i) for i in bag_ids][:self.PARTY_MAX]
        self.set_meta("active_party", _json.dumps(clean))
        self.set_meta("active_bag_id", str(clean[0]))

    def add_to_party(self, bag_id: int) -> bool:
        """Append a buddy to the party. Returns False if the party is
        already at PARTY_MAX (caller surfaces a friendly message)."""
        party = self.load_active_party()
        if bag_id in party:
            return True
        if len(party) >= self.PARTY_MAX:
            return False
        party.append(bag_id)
        self.save_active_party(party)
        return True

    def remove_from_party(self, bag_id: int) -> bool:
        """Drop a buddy from the party. Refuses when it would leave the
        party empty — must always have at least one active buddy."""
        party = self.load_active_party()
        if bag_id not in party or len(party) <= 1:
            return False
        party.remove(bag_id)
        self.save_active_party(party)
        return True

    def party_slot(self, bag_id: int) -> Optional[int]:
        """0-based slot if the buddy is in the party, else None."""
        party = self.load_active_party()
        return party.index(bag_id) if bag_id in party else None

    # ---------- bag ----------
    def list_bag(self) -> List[Buddy]:
        rows = self.conn.execute(
            "SELECT * FROM bag ORDER BY id"
        ).fetchall()
        return [self._row_to_buddy(r) for r in rows]

    def get_bag_entry(self, bag_id: int) -> Optional[Buddy]:
        row = self.conn.execute("SELECT * FROM bag WHERE id=?",
                                (bag_id,)).fetchone()
        return self._row_to_buddy(row) if row else None

    def add_to_bag(self, dex_id: int, *, is_rare: bool = False,
                   nickname: Optional[str] = None,
                   caught_with: str = "pokeball.basic",
                   personality: Optional[str] = None) -> Buddy:
        """Create a new individual of `dex_id`. Stats are baked-in here
        rather than relying on the bag table's SQL DEFAULTs — earlier app
        versions created the table with `friendship DEFAULT 30`, and on
        existing DBs that legacy DEFAULT was still applying to new catches
        (newly-caught wild Pokemon were showing up at fr=30 instead of 0).
        Passing every nominally-default value explicitly avoids that trap."""
        import random as _r
        if personality is None:
            personality = _r.choice(
                ["playful", "calm", "brave", "shy", "naive", "smart"]
            )
        now = time.time()
        cur = self.conn.execute(
            "INSERT INTO bag(dex_id, is_rare, nickname, level, exp, "
            "friendship, friendship_xp, caught_with, personality, "
            "nickname_history, last_interaction_at, caught_at) "
            "VALUES(?,?,?,1,0,0,0,?,?,'[]',?,?)",
            (dex_id, int(is_rare), nickname, caught_with, personality,
             now, now),
        )
        self.conn.commit()
        return self.get_bag_entry(cur.lastrowid)  # type: ignore[return-value]

    def remove_from_bag(self, bag_id: int) -> None:
        # Drop from party first so the party list doesn't reference a
        # ghost bag entry. We don't enforce the "min 1" rule here — the
        # caller is responsible for ensuring at least one bag entry
        # remains as a viable primary.
        party = self.load_active_party()
        if bag_id in party and len(party) > 1:
            party.remove(bag_id)
            self.save_active_party(party)
        self.conn.execute("DELETE FROM bag WHERE id=?", (bag_id,))
        # Also remove the per-buddy window position so a future buddy
        # with the same id (won't happen with AUTOINCREMENT, but defensive)
        # doesn't inherit stale coordinates.
        self.conn.execute(
            "DELETE FROM meta WHERE key=? OR key=?",
            (f"win_x_{bag_id}", f"win_y_{bag_id}"),
        )
        self.conn.commit()

    def rename_bag_entry(self, bag_id: int, nickname: Optional[str]) -> None:
        """Update the buddy's current nickname AND append the change to
        the nickname_history JSON log so the detail dialog can show the
        full naming history."""
        import json as _j
        row = self.conn.execute(
            "SELECT nickname_history FROM bag WHERE id=?", (bag_id,),
        ).fetchone()
        if row is None:
            return
        try:
            history = _j.loads(row["nickname_history"] or "[]")
        except ValueError:
            history = []
        history.append({
            "nickname": nickname or "",
            "set_at": time.time(),
        })
        self.conn.execute(
            "UPDATE bag SET nickname=?, nickname_history=? WHERE id=?",
            (nickname, _j.dumps(history, ensure_ascii=False), bag_id),
        )
        self.conn.commit()

    def evolve_active_buddy(self, new_dex_id: int) -> None:
        """Change the active bag entry's species in place — same individual,
        new form. Stats (including is_rare) are preserved."""
        bag_str = self.get_meta("active_bag_id")
        if not bag_str:
            return
        try:
            bag_id = int(bag_str)
        except ValueError:
            return
        self.evolve_bag_entry(bag_id, new_dex_id)

    def evolve_bag_entry(self, bag_id: int, new_dex_id: int) -> None:
        """Evolve a specific individual by bag_id (not active_bag_id).
        Called by BuddyApp when an evolution stone is applied to a buddy
        that isn't the current primary."""
        self.conn.execute(
            "UPDATE bag SET dex_id=? WHERE id=?", (new_dex_id, bag_id),
        )
        self.conn.commit()

    def close(self) -> None:
        """Close the SQLite connection. Safe to call multiple times."""
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:  # noqa: BLE001
                pass
            self.conn = None  # type: ignore[assignment]

    # ---------- mechanics ----------
    def apply_friendship_decay(self, b: Buddy,
                               now: Optional[float] = None) -> Buddy:
        """No-op as of 2026-05-19.

        This used to drift friendship down 1/day after 48h of no
        interaction, measured on wall-clock time. That model penalized the
        user for normal work-buddy patterns — PC off overnight + weekends
        looks identical to "neglecting the Pokemon" from
        `last_interaction_at`'s perspective. The buddy lives on a work
        computer, so the user explicitly does NOT want decay during
        off-hours.

        Instead, absence is surfaced through `daily_schedule` + welcome-back
        lines: when the user shows up after 24h+, the buddy says "오랜만이야"
        — friendship itself stays put."""
        return b

    def gain_exp(self, b: Buddy, amount: int) -> bool:
        from .config import FRIENDSHIP_BONUS_HIGH, FRIENDSHIP_BONUS_MID
        multiplier = 1.0
        if b.friendship >= FRIENDSHIP_BONUS_HIGH:
            multiplier = 1.5
        elif b.friendship >= FRIENDSHIP_BONUS_MID:
            multiplier = 1.2
        gained = int(round(amount * multiplier))
        b.exp += gained
        leveled = False
        while b.exp >= b.exp_to_next:
            b.exp -= b.exp_to_next
            b.level += 1
            leveled = True
        self.save_active_buddy(b)
        return leveled

    def bump_friendship(self, b: Buddy, xp_delta: int) -> None:
        """Add `xp_delta` toward the next friendship point. Once the buddy's
        XP accumulator crosses FRIENDSHIP_XP_PER_POINT, the visible friendship
        integer goes up by 1 and the accumulator resets. Negative deltas
        drain the accumulator but never pull friendship itself down — that's
        what `apply_friendship_decay` is for."""
        from .config import FRIENDSHIP_XP_PER_POINT
        b.friendship_xp += int(xp_delta)
        while b.friendship_xp >= FRIENDSHIP_XP_PER_POINT and b.friendship < 100:
            b.friendship_xp -= FRIENDSHIP_XP_PER_POINT
            b.friendship += 1
        if b.friendship >= 100:
            # Cap reached — discard residual XP so the bar stays at full.
            b.friendship = 100
            b.friendship_xp = 0
        if b.friendship_xp < 0:
            b.friendship_xp = 0
        b.last_interaction_at = time.time()
        self.save_active_buddy(b)

    def bump_friendship_points(self, b: Buddy, points: int) -> None:
        """Add whole-point friendship instantly — used by potion items and
        any other effect that should bypass the slow XP grind."""
        from .config import FRIENDSHIP_XP_PER_POINT
        self.bump_friendship(b, points * FRIENDSHIP_XP_PER_POINT)

    # ---------- reminders ----------
    def _ensure_default_reminders(self) -> None:
        if self.get_meta("reminders_seeded") == "1":
            return
        now = time.time()
        for name, message, interval in DEFAULT_REMINDERS:
            self.conn.execute(
                "INSERT INTO reminders(name, message, interval_min, "
                "enabled, last_fired_at) VALUES(?,?,?,1,?)",
                (name, message, interval, now),
            )
        self.conn.commit()
        self.set_meta("reminders_seeded", "1")

    def _row_to_reminder(self, row: sqlite3.Row) -> Reminder:
        return Reminder(
            id=row["id"],
            name=row["name"],
            message=row["message"],
            interval_min=row["interval_min"],
            enabled=bool(row["enabled"]),
            last_fired_at=row["last_fired_at"],
        )

    def list_reminders(self) -> List[Reminder]:
        rows = self.conn.execute("SELECT * FROM reminders ORDER BY id").fetchall()
        return [self._row_to_reminder(r) for r in rows]

    def upsert_reminder(self, r: Reminder) -> int:
        if r.id is None:
            cur = self.conn.execute(
                "INSERT INTO reminders(name, message, interval_min, enabled, "
                "last_fired_at) VALUES(?,?,?,?,?)",
                (r.name, r.message, r.interval_min, int(r.enabled),
                 r.last_fired_at),
            )
            self.conn.commit()
            r.id = cur.lastrowid
            return cur.lastrowid
        self.conn.execute(
            "UPDATE reminders SET name=?, message=?, interval_min=?, "
            "enabled=?, last_fired_at=? WHERE id=?",
            (r.name, r.message, r.interval_min, int(r.enabled),
             r.last_fired_at, r.id),
        )
        self.conn.commit()
        return r.id

    def delete_reminder(self, reminder_id: int) -> None:
        self.conn.execute("DELETE FROM reminders WHERE id=?", (reminder_id,))
        self.conn.commit()

    def mark_reminder_fired(self, reminder_id: int,
                            when: Optional[float] = None) -> None:
        self.conn.execute(
            "UPDATE reminders SET last_fired_at=? WHERE id=?",
            (when if when is not None else time.time(), reminder_id),
        )
        self.conn.commit()

    # ---------- dex (species registry) ----------
    def _row_to_dex(self, row: sqlite3.Row) -> DexEntry:
        return DexEntry(
            dex_id=row["dex_id"],
            is_rare=bool(row["is_rare"]),
            name=row["name"],
            first_caught_at=row["first_caught_at"],
            last_caught_at=row["last_caught_at"],
            count=row["count"],
        )

    def list_dex(self) -> List[DexEntry]:
        rows = self.conn.execute(
            "SELECT * FROM dex ORDER BY dex_id, is_rare"
        ).fetchall()
        return [self._row_to_dex(r) for r in rows]

    def get_dex_entry(self, dex_id: int,
                      is_rare: bool = False) -> Optional[DexEntry]:
        row = self.conn.execute(
            "SELECT * FROM dex WHERE dex_id=? AND is_rare=?",
            (dex_id, int(is_rare)),
        ).fetchone()
        return self._row_to_dex(row) if row else None

    def record_catch(self, dex_id: int, name: str, *,
                     is_rare: bool = False) -> DexEntry:
        """Register that a species (normal or rare variant) has been caught
        at the dex level. Bag entries are managed separately by `add_to_bag`."""
        now = time.time()
        existing = self.get_dex_entry(dex_id, is_rare=is_rare)
        if existing is None:
            self.conn.execute(
                "INSERT INTO dex(dex_id, is_rare, name, first_caught_at, "
                "last_caught_at, count) VALUES(?,?,?,?,?,1)",
                (dex_id, int(is_rare), name, now, now),
            )
        else:
            self.conn.execute(
                "UPDATE dex SET count = count + 1, last_caught_at=?, name=? "
                "WHERE dex_id=? AND is_rare=?",
                (now, name, dex_id, int(is_rare)),
            )
        self.conn.commit()
        return self.get_dex_entry(dex_id, is_rare=is_rare)  # type: ignore[return-value]

    # ---------- starter items ----------
    def _ensure_starter_items(self) -> None:
        """One-time seed of a small inventory pack so the user can feed,
        play, and catch right away on a fresh install (or after reset).
        Idempotent via meta.starter_items_seeded."""
        if self.get_meta("starter_items_seeded") == "1":
            return
        starter = [
            ("food.apple",     3),
            ("food.berry",     1),
            ("toy.ball",       2),
            ("pokeball.basic", 5),
        ]
        for key, n in starter:
            self.conn.execute(
                "INSERT INTO inventory(item_key, count) VALUES(?, ?) "
                "ON CONFLICT(item_key) DO UPDATE SET count = count + excluded.count",
                (key, n),
            )
        self.conn.commit()
        self.set_meta("starter_items_seeded", "1")

    # ---------- daily schedule events ----------
    def _ensure_default_schedule_events(self) -> None:
        """Seed the three fixed scheduled events (출근/점심/퇴근) from the
        config-file defaults on first run. After that the times live in
        the DB so the user can edit them from the UI."""
        if self.get_meta("schedule_events_seeded") == "1":
            return
        from .config import (
            LUNCH_HOUR, LUNCH_MINUTE,
            WORK_END_HOUR, WORK_END_MINUTE,
            WORK_START_HOUR, WORK_START_MINUTE,
        )
        defaults = [
            ("morning",  WORK_START_HOUR, WORK_START_MINUTE),
            ("lunch",    LUNCH_HOUR,      LUNCH_MINUTE),
            ("farewell", WORK_END_HOUR,   WORK_END_MINUTE),
        ]
        for key, h, m in defaults:
            self.conn.execute(
                "INSERT OR IGNORE INTO daily_events(key, hour, minute, enabled) "
                "VALUES(?,?,?,1)",
                (key, h, m),
            )
        self.set_meta("schedule_events_seeded", "1")
        self.conn.commit()

    def _row_to_daily_event(self, row: sqlite3.Row) -> DailyEvent:
        key = row["key"]
        is_builtin = key in BUILTIN_EVENT_KEYS
        label = (row["label"] if row["label"]
                 else DAILY_EVENT_LABELS.get(key, "알람"))
        return DailyEvent(
            key=key,
            label=label,
            hour=int(row["hour"]),
            minute=int(row["minute"]),
            enabled=bool(row["enabled"]),
            message=row["message"] or "",
            is_builtin=is_builtin,
        )

    def list_schedule_events(self) -> List["DailyEvent"]:
        """All alarms, built-ins first in canonical order, custom alarms
        after that sorted by clock time."""
        rows = self.conn.execute(
            "SELECT key, hour, minute, enabled, label, message "
            "FROM daily_events"
        ).fetchall()
        by_key = {r["key"]: r for r in rows}
        out: List[DailyEvent] = []
        for key in DAILY_EVENT_ORDER:
            r = by_key.pop(key, None)
            if r is None:
                continue
            out.append(self._row_to_daily_event(r))
        # Customs, sorted by hour/minute then by key for stability.
        customs = sorted(by_key.values(),
                         key=lambda r: (r["hour"], r["minute"], r["key"]))
        for r in customs:
            out.append(self._row_to_daily_event(r))
        return out

    def update_schedule_event(self, key: str, hour: int, minute: int,
                              enabled: bool, *,
                              label: Optional[str] = None,
                              message: Optional[str] = None) -> None:
        """Upsert a single event. `label`/`message` are optional — passing
        None leaves whatever's currently in the DB untouched so callers
        that only want to retime a built-in don't need to know its label."""
        h = max(0, min(23, int(hour)))
        m = max(0, min(59, int(minute)))
        # Read existing row so we preserve fields the caller didn't supply.
        existing = self.conn.execute(
            "SELECT label, message FROM daily_events WHERE key=?", (key,),
        ).fetchone()
        if existing is not None:
            final_label = label if label is not None else existing["label"]
            final_message = message if message is not None else existing["message"]
        else:
            final_label = label or ""
            final_message = message or ""
        self.conn.execute(
            "INSERT INTO daily_events(key, hour, minute, enabled, label, message) "
            "VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET hour=excluded.hour, "
            "minute=excluded.minute, enabled=excluded.enabled, "
            "label=excluded.label, message=excluded.message",
            (key, h, m, int(enabled), final_label, final_message),
        )
        self.conn.commit()

    def add_custom_alarm(self, label: str, message: str,
                         hour: int, minute: int,
                         enabled: bool = True) -> str:
        """Create a custom (deletable) alarm and return its generated key."""
        import secrets
        key = f"custom_{secrets.token_hex(4)}"
        self.update_schedule_event(
            key, hour, minute, enabled,
            label=label, message=message,
        )
        return key

    def delete_schedule_event(self, key: str) -> bool:
        """Delete a custom alarm. Built-in events are protected — the user
        should disable them instead (their banks are wired up in code)."""
        if key in BUILTIN_EVENT_KEYS:
            return False
        cur = self.conn.execute(
            "DELETE FROM daily_events WHERE key=?", (key,)
        )
        self.conn.commit()
        # Also drop the per-day-fired meta so a recreated alarm at the same
        # key can fire again. (Same-key recreation is unlikely with random
        # hex keys, but the cleanup is cheap.)
        self.conn.execute(
            "DELETE FROM meta WHERE key=?",
            (f"daily_{key}_last_fired",),
        )
        self.conn.commit()
        return cur.rowcount > 0

    # ---------- inventory ----------
    def get_item_count(self, key: str) -> int:
        row = self.conn.execute(
            "SELECT count FROM inventory WHERE item_key=?", (key,),
        ).fetchone()
        return int(row["count"]) if row else 0

    def add_item(self, key: str, n: int = 1) -> int:
        """Add n of an item; returns the new total."""
        self.conn.execute(
            "INSERT INTO inventory(item_key, count) VALUES(?, ?) "
            "ON CONFLICT(item_key) DO UPDATE SET count = count + excluded.count",
            (key, n),
        )
        self.conn.commit()
        return self.get_item_count(key)

    def consume_item(self, key: str, n: int = 1) -> bool:
        """Decrement an item's count by n if available. Returns True on
        success, False if there wasn't enough. Atomic via the WHERE clause."""
        cur = self.conn.execute(
            "UPDATE inventory SET count = count - ? "
            "WHERE item_key=? AND count >= ?",
            (n, key, n),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def list_inventory(self) -> List[tuple]:
        """All inventory rows with count > 0 as (key, count). Ordered by key
        so the UI is stable."""
        rows = self.conn.execute(
            "SELECT item_key, count FROM inventory WHERE count > 0 "
            "ORDER BY item_key"
        ).fetchall()
        return [(r["item_key"], int(r["count"])) for r in rows]

    def total_of_kind(self, kind: str) -> int:
        """Sum of all item counts whose key starts with `<kind>.` — e.g.,
        total_of_kind('food') sums every food.* row."""
        prefix = f"{kind}."
        row = self.conn.execute(
            "SELECT COALESCE(SUM(count), 0) AS total FROM inventory "
            "WHERE item_key LIKE ?",
            (prefix + "%",),
        ).fetchone()
        return int(row["total"]) if row else 0

    def first_available_of_kind(self, kind: str) -> Optional[str]:
        """Return the item_key of the first row with count > 0 for the given
        kind, or None. Used by feed/play to pick what to consume."""
        prefix = f"{kind}."
        row = self.conn.execute(
            "SELECT item_key FROM inventory WHERE item_key LIKE ? AND count > 0 "
            "ORDER BY item_key LIMIT 1",
            (prefix + "%",),
        ).fetchone()
        return row["item_key"] if row else None

    # ---------- reset ----------
    def reset_all_data(self) -> None:
        """Wipe gameplay state (bag, dex, inventory, active pointer) and
        reseed the starter. Preserves reminders, window position, sprite
        style preference, and migration flags."""
        self.conn.executescript("""
            DELETE FROM bag;
            DELETE FROM dex;
            DELETE FROM inventory;
            DELETE FROM buddy;
        """)
        # Drop runtime pointers + starter-item gate so the user gets the
        # starter pack again on a fresh slate.
        self.conn.execute(
            "DELETE FROM meta WHERE key IN "
            "('active_bag_id', 'active_dex_id', "
            " 'last_greeting_date', 'last_encounter_at', "
            " 'last_item_drop_at', 'starter_items_seeded', "
            " 'master_ball_pending', "
            " 'daily_morning_last_fired', 'daily_lunch_last_fired', "
            " 'daily_farewell_last_fired')"
        )
        self.conn.commit()
        # Reseed the starter buddy + starter inventory.
        self._ensure_active_buddy()
        self._ensure_starter_items()
