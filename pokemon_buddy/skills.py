"""Pokemon techniques ("기술") a buddy can learn.

A skill is a passive ability tied to an individual buddy (stored as a key in
the bag row's `skills` JSON list — see state.Buddy.learned_skills). There are
two ways to learn one:

  1) Teaching scroll (두루마리): a rare on-screen drop. Collecting it banks a
     `skill.<key>` scroll in the inventory; using the scroll teaches the skill
     to a chosen party member.
  2) Bond mastery: a buddy at full friendship (100) auto-learns the skill the
     next time it levels up — no scroll required.

Currently one skill exists — 수집광 (collector). The catalog is a dict so more
can slot in later without touching call sites."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


# Skill keys (stored verbatim in bag.skills).
SKILL_COLLECTOR = "collector"


@dataclass(frozen=True)
class SkillDef:
    key: str            # e.g. "collector"
    name: str           # Korean display name, e.g. "수집광"
    emoji: str          # decorative glyph
    item_key: str       # the teaching-scroll inventory key (items.py)
    description: str     # one-line effect summary for UI / messages


SKILLS: Dict[str, SkillDef] = {
    SKILL_COLLECTOR: SkillDef(
        key=SKILL_COLLECTOR,
        name="수집광",
        emoji="📜",
        item_key="skill.collector",
        description=(
            "화면에 아이템이 떨어지면 잠시 뒤 끌어당겨 자동으로 주워와."
        ),
    ),
}

# Reverse lookup: teaching-scroll item key -> skill key.
SKILL_BY_ITEM_KEY: Dict[str, str] = {s.item_key: k for k, s in SKILLS.items()}


def find(skill_key: str) -> Optional[SkillDef]:
    return SKILLS.get(skill_key)


def skill_for_item(item_key: str) -> Optional[SkillDef]:
    """The skill a teaching scroll grants, or None if the item isn't a scroll."""
    key = SKILL_BY_ITEM_KEY.get(item_key)
    return SKILLS.get(key) if key else None
