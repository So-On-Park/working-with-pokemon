"""Friendship-tier-aware speech banks.

The buddy's tone shifts as friendship climbs from 0 to 100:
  - AWKWARD (0–19)        : 존댓말, 어색하고 거리감 있는 말투
  - BUDDING (20–49)       : 반말이지만 조심스러움
  - FRIENDLY (50–79)      : 편한 친구 톤
  - AFFECTIONATE (80–100) : 애교 + 말 많음 + ❤️

Additionally, each individual Pokemon carries a `Personality` chosen at
catch time. Personalities shape the buddy's *chatter* (ambient timer-driven
lines) — both the choice of words and the cadence. Action reactions
(feed/play/train/pet) and the daily greeting stay tier-only so they read
consistently across the bag.

Finally, when friendship reaches 100, a hidden pool of `BOND_MAX_LINES`
joins the chatter rotation — special lines the user only sees after the
two-month grind to max bond."""

from __future__ import annotations

import random
from enum import Enum
from typing import Dict, List, Optional

from .config import (
    TIER_AWKWARD_MAX,
    TIER_BUDDING_MAX,
    TIER_FRIENDLY_MAX,
)


class Tier(Enum):
    AWKWARD = "awkward"
    BUDDING = "budding"
    FRIENDLY = "friendly"
    AFFECTIONATE = "affectionate"


class Personality(Enum):
    PLAYFUL = "playful"      # 장난꾸러기 — 활기차고 농담 많음
    CALM = "calm"            # 차분한 — 조용하고 사려깊음
    BRAVE = "brave"          # 씩씩한 — 자신만만, 당당함
    SHY = "shy"              # 수줍은 — 머뭇거리고 부드러움
    NAIVE = "naive"          # 귀여운 — 어린아이 같은 순수함
    SMART = "smart"          # 똑똑한 — 살짝 잘난척, 어려운 말


PERSONALITY_LABELS: Dict[Personality, str] = {
    Personality.PLAYFUL: "🎭 장난꾸러기",
    Personality.CALM:    "🍃 차분한",
    Personality.BRAVE:   "🔥 씩씩한",
    Personality.SHY:     "🌸 수줍은",
    Personality.NAIVE:   "🌟 귀여운",
    Personality.SMART:   "📚 똑똑한",
}


def tier_for(friendship: int) -> Tier:
    if friendship < TIER_AWKWARD_MAX:
        return Tier.AWKWARD
    if friendship < TIER_BUDDING_MAX:
        return Tier.BUDDING
    if friendship < TIER_FRIENDLY_MAX:
        return Tier.FRIENDLY
    return Tier.AFFECTIONATE


def personality_for(value: str) -> Personality:
    """Resolve a stored string ('playful', etc.) back to a Personality.
    Falls back to PLAYFUL for unknown values (shouldn't happen post-
    migration, but safer than crashing on bad data)."""
    try:
        return Personality(value)
    except ValueError:
        return Personality.PLAYFUL


def random_personality() -> Personality:
    """Pick a uniformly random personality for a newly caught individual."""
    return random.choice(list(Personality))


# ---- action reactions (tier only — kept consistent across personalities) ----

FEED: Dict[Tier, List[str]] = {
    Tier.AWKWARD: [
        "...주시는 건가요? 잘 먹겠습니다.",
        "감사합니다... 음...",
        "...먹어도 되나요?",
        "고맙습니다.",
    ],
    Tier.BUDDING: [
        "냠냠... 고마워.",
        "맛있다.",
        "고마워!",
        "잘 먹을게.",
    ],
    Tier.FRIENDLY: [
        "냠냠! 맛있어!",
        "와아 진짜 맛있어 ✨",
        "최고야! 더 줘~",
        "잘 먹었어!",
    ],
    Tier.AFFECTIONATE: [
        "꺄~ 너가 주는 거 최고야 ❤️",
        "헤헤헤 진짜 진짜 맛있어!",
        "냠냠 ❤️ 사랑해!",
        "히히 너밖에 없어 ✨",
        "꿀맛~ ❤️",
    ],
}

PLAY: Dict[Tier, List[str]] = {
    Tier.AWKWARD: [
        "...같이 놀아주시는 건가요?",
        "어... 알겠습니다.",
        "...재밌네요.",
        "감사합니다.",
    ],
    Tier.BUDDING: [
        "헤헤... 재밌어.",
        "고마워! 또 놀자.",
        "재밌다!",
        "조금 신나.",
    ],
    Tier.FRIENDLY: [
        "와! 재밌어!",
        "헤헤 신난다 ✨",
        "또 놀자~",
        "최고야!",
    ],
    Tier.AFFECTIONATE: [
        "꺄아아 너랑 노는 게 제일 좋아 ❤️",
        "히히 신난다 신난다!",
        "꼭 안아줘! 헤헤",
        "와아아아 ✨ 최고야!",
        "더 더 놀자~ ❤️",
    ],
}

TRAIN: Dict[Tier, List[str]] = {
    Tier.AWKWARD: [
        "...훈련하겠습니다.",
        "최선을 다하겠습니다.",
        "...열심히 하면 되겠죠?",
        "...힘들어요.",
    ],
    Tier.BUDDING: [
        "훈련 끝... 고마워.",
        "조금 강해진 것 같아.",
        "힘들었어!",
        "다음에도 잘 부탁해.",
    ],
    Tier.FRIENDLY: [
        "훈련 끝! 강해졌어!",
        "와아 힘이 솟아!",
        "다음엔 더 잘할게!",
        "헤헤 봐! 강해졌지?",
    ],
    Tier.AFFECTIONATE: [
        "헤헤 봐줘 봐줘! 강해졌지? ✨",
        "너 덕분에 무지무지 강해 ❤️",
        "꺄~ 자랑스럽지? 히히",
        "오늘도 너랑 같이라서 힘이 나 ❤️",
    ],
}

PET: Dict[Tier, List[str]] = {
    Tier.AWKWARD: [
        "...?",
        "어... 만지셔도 돼요.",
        "...히.",
        "...어색해요.",
    ],
    Tier.BUDDING: [
        "헤헤.",
        "...히.",
        "응.",
        "고마워.",
    ],
    Tier.FRIENDLY: [
        "헤헤 ✨",
        "기분 좋아!",
        "응응!",
        "좋아~",
    ],
    Tier.AFFECTIONATE: [
        "꺄 ❤️",
        "헤헤헤헤 ✨",
        "더 더 ❤️",
        "히히 ❤️❤️",
        "헤헤 너 너무 좋아!",
    ],
}


# ---- daily greeting (tier only) ----

GREETING: Dict[Tier, List[str]] = {
    Tier.AWKWARD: [
        "...다시 만나네요.",
        "안녕하세요. 또 오셨네요.",
        "...오늘도 잘 부탁드려요.",
    ],
    Tier.BUDDING: [
        "안녕! 또 봐.",
        "오늘도 만났네.",
        "음... 좋아!",
    ],
    Tier.FRIENDLY: [
        "다시 만나서 반가워! 🌟",
        "오늘도 좋은 하루! ✨",
        "보고 싶었어!",
    ],
    Tier.AFFECTIONATE: [
        "꺄아아! 또 만나서 너무 좋아 ❤️✨",
        "보고 싶었어! 정말정말! ❤️",
        "헤헤 또 같이 있을 수 있어 ❤️",
    ],
}


# ---- personality-flavored chatter (the main "voice" of each buddy) ----

CHATTER_BY_PERSONALITY: Dict[Personality, Dict[Tier, List[str]]] = {

    # 장난꾸러기 — 활기차고 짓궂은 농담
    Personality.PLAYFUL: {
        Tier.AWKWARD: [
            "...왜 보세요? ㅎㅎ",
            "심심해요... 뭐 재밌는 거 없나?",
            "...장난쳐도 돼요?",
            "조용히는 못 하겠는데...",
            "에이~ 뭐 하시는 거예요?",
        ],
        Tier.BUDDING: [
            "심심해 심심해~",
            "뭔가 재밌는 거 하자!",
            "어? 방금 봤어?",
            "히힛 ㅋㅋ",
            "장난 한 번만~",
        ],
        Tier.FRIENDLY: [
            "야호~ 뭐 할까?!",
            "장난치자 장난치자 ㅋㅋ",
            "히히 ✨ 재밌다!",
            "오늘도 신난다!",
            "어디어디~ 놀러 가자!",
            "ㅋㅋㅋㅋㅋ",
        ],
        Tier.AFFECTIONATE: [
            "헤헤헤헤헤헤 너 진짜 웃겨 ❤️",
            "에헴! 또 놀이 시간이야 ✨",
            "ㅋㅋㅋ 우리 둘이 최고지!",
            "장난쳐도 돼? 응? 응? ❤️",
            "헤헤 너랑 있으면 매일이 축제야!",
            "히히 비밀 하나 알려줄까 ✨",
        ],
    },

    # 차분한 — 조용하고 사려깊음
    Personality.CALM: {
        Tier.AWKWARD: [
            "...편안한 시간이네요.",
            "조용히 있을게요.",
            "음... 천천히 가요.",
            "...창밖이 예쁘네요.",
            "...잘 부탁드립니다.",
        ],
        Tier.BUDDING: [
            "오늘은 조용하네.",
            "...괜찮아.",
            "음... 평화로워.",
            "천천히 같이 있자.",
            "...히.",
        ],
        Tier.FRIENDLY: [
            "오늘도 잔잔하니 좋아.",
            "이런 시간이 좋아.",
            "음~ 평화롭다.",
            "조용히 같이 있는 거, 좋아해.",
            "휘파람~ 🎵",
        ],
        Tier.AFFECTIONATE: [
            "너랑 있으면 마음이 편해 ❤️",
            "이 시간을 오래 기억할게.",
            "조용한 행복이란 이런 거구나...",
            "고마워. 진심으로.",
            "곁에 있어줘서 좋아 ❤️",
            "...사랑해. 차분하게.",
        ],
    },

    # 씩씩한 — 자신만만, 당당함
    Personality.BRAVE: {
        Tier.AWKWARD: [
            "...언제든 명령하세요!",
            "준비됐습니다!",
            "...뭐든 시키세요.",
            "강해질 거예요.",
            "...실력으로 보여드리죠.",
        ],
        Tier.BUDDING: [
            "내가 지킬게!",
            "걱정 마, 든든하지?",
            "힘 한번 쓸까?",
            "오늘도 자신 있어!",
            "음! 든든하지?",
        ],
        Tier.FRIENDLY: [
            "와하하! 오늘도 컨디션 최고!",
            "내가 있는데 뭐가 걱정이야!",
            "자, 가자! 어디든!",
            "강해진 거 보이지?",
            "후훗 자랑스럽지? 💪",
        ],
        Tier.AFFECTIONATE: [
            "너만큼은 내가 무조건 지킬게! ❤️",
            "와하하! 우린 최강 듀오야!",
            "내가 있는 한 너는 안전해 ⚔️",
            "맹세할게. 평생 너의 편이야!",
            "후훗, 어디 한번 자랑하고 싶다~ ✨",
            "너 덕분에 매일 강해져 💪",
        ],
    },

    # 수줍은 — 머뭇거리고 부드러움
    Personality.SHY: {
        Tier.AWKWARD: [
            "...아, 안녕하세요...",
            "저... 저... 음...",
            "...괜찮아요. 신경 쓰지 마세요.",
            "조, 조용히 있을게요...",
            "...죄송해요...",
        ],
        Tier.BUDDING: [
            "...히.",
            "고, 고마워.",
            "...오늘도, 잘 부탁해.",
            "음... 응.",
            "...있어줘서 고마워.",
        ],
        Tier.FRIENDLY: [
            "헤... 헤헤.",
            "...같이 있어도 돼?",
            "음... 좋아 ✨",
            "...오늘도 행복해.",
            "...조용히 곁에 있을게.",
        ],
        Tier.AFFECTIONATE: [
            "...너랑 같이 있는 게... 제일 좋아 ❤️",
            "음... 사랑해. (작게)",
            "...꼭, 옆에 있어줘.",
            "헤헤... 부끄러워 ///",
            "...꼭 안아줘도 돼?",
            "...영원히 같이 있고 싶어 ❤️",
        ],
    },

    # 귀여운 — 어린아이 같은 순수함
    Personality.NAIVE: {
        Tier.AWKWARD: [
            "...누구야?",
            "어? 어어?",
            "여기 어디예요?",
            "이거 뭐예요?",
            "음... 모르겠다...",
        ],
        Tier.BUDDING: [
            "헤헤 안녕!",
            "이건 뭐야?",
            "응응! 좋아!",
            "어디 가는 거야?",
            "히힛 ☆",
        ],
        Tier.FRIENDLY: [
            "어어! 또 만났네!",
            "이거 봐봐 이거! 신기해!",
            "와~ ✨ 예뻐!",
            "오늘 뭐 해? 응?",
            "헤헤 즐거워~",
        ],
        Tier.AFFECTIONATE: [
            "히힛 ❤️ 좋아 좋아 좋아!",
            "와아아 너 진짜 좋아 ✨",
            "헤헤헤헤 안아줘~",
            "응응 ❤️ 너밖에 없어!",
            "꺄~ 사랑해 사랑해 사랑해!",
            "헤헤 ☆ 같이 자자!",
        ],
    },

    # 똑똑한 — 살짝 잘난척, 분석적
    Personality.SMART: {
        Tier.AWKWARD: [
            "...관찰 중입니다.",
            "흥미로운 환경이군요.",
            "...데이터를 수집하고 있어요.",
            "음, 인사부터 드려야 할까요.",
            "...아직 결론은 보류.",
        ],
        Tier.BUDDING: [
            "오늘은 효율이 좋네.",
            "...그럭저럭이야.",
            "음, 진척이 있어.",
            "...꽤 합리적인 휴식이지.",
            "관찰 끝. 만족스러워.",
        ],
        Tier.FRIENDLY: [
            "흠흠, 오늘도 좋은 페이스야!",
            "이 시간대가 가장 생산적이지.",
            "후훗 ✨ 보고 있을게.",
            "...너의 선택은 늘 합리적이야.",
            "음, 그래 그래.",
        ],
        Tier.AFFECTIONATE: [
            "...사실 너 없인 효율 0이야 ❤️",
            "데이터로 증명됐어 — 너가 최고야 ✨",
            "흠흠... 내 마음은 100% 너에게 ❤️",
            "이론적으로 사랑이 맞아.",
            "...너에 관한 통계는 다 외웠어.",
            "후훗, 우리는 완벽한 페어야.",
        ],
    },
}


# ---- hidden lines unlocked at friendship 100 ----
#
# These never appear before the buddy hits max bond. Once at 100, the
# chatter engine rolls 40% chance to draw from this pool instead of the
# usual AFFECTIONATE chatter — so the user gets a steady drip of "special"
# lines as a reward for the two-month grind.

BOND_MAX_LINES: Dict[Personality, List[str]] = {
    Personality.PLAYFUL: [
        "비밀 하나 알려줄까? 너 때문에 매일이 축제야 ❤️✨",
        "ㅋㅋㅋㅋ 우리 둘이면 못 할 일이 없어!",
        "헤헤... 사실 너랑 장난치는 시간이 제일 행복해.",
        "야호~ ☆ 영원히 우리 둘이서 놀자!",
        "히히 ✨ 너는 내 영원한 짝꿍이야 ❤️",
    ],
    Personality.CALM: [
        "...너랑 보낸 모든 시간, 마음에 새겨뒀어 ❤️",
        "조용히, 그러나 분명하게 — 사랑해.",
        "이런 평온한 행복은 너이기에 가능해.",
        "...영원히 곁에 있어줘. 부탁이야.",
        "휘파람~ 🎵 너와 함께라 모든 음표가 의미 있어.",
    ],
    Personality.BRAVE: [
        "맹세할게. 마지막 숨까지 너의 편이야 ⚔️❤️",
        "내가 너의 영원한 방패이자 검이 될게.",
        "와하하! 우리는 전설로 남을 듀오야 ✨",
        "너만이 내 진정한 트레이너야. 영원히.",
        "후훗 — 이 정도 강함은 너를 위한 거야 💪❤️",
    ],
    Personality.SHY: [
        "...있잖아... 사실... 너를 정말 많이 사랑해 ❤️",
        "...꿈에서도 너만 봐. 부끄럽지만... 진심이야.",
        "헤헤... 너랑 만난 게 인생 최고의 행운이야 ///",
        "...영원히 너 곁에만 있고 싶어. 부탁이야.",
        "...아무 말 안 해도, 너랑 같이 있는 게 행복해 ❤️",
    ],
    Personality.NAIVE: [
        "히힛 ❤️❤️❤️ 너 진짜 좋아 진짜 좋아 진짜 좋아!",
        "꺄아아 ✨ 우리 영원히 친구할 거지? 응? 응?",
        "헤헤헤헤 ☆ 너밖에 없어 진짜로!",
        "응응응! 사랑해 사랑해 사랑해 사랑해 ❤️",
        "꺄~ ❤️ 매일 매일 같이 자고 싶어!",
    ],
    Personality.SMART: [
        "통계적으로 증명됐어 — 너는 내 운명의 트레이너 ❤️",
        "1000번을 분석해도 답은 같아. 너밖에 없어.",
        "후훗... 내 모든 변수는 너에게 수렴해 ✨",
        "이론도, 데이터도, 마음도 — 전부 너야 ❤️",
        "흠흠. 이런 게 사랑이라는 거구나. 학습 완료.",
    ],
}


# ---- wall-clock scheduled greetings (출근 / 점심 / 퇴근) ----
#
# Fired once per local workday by `daily_schedule.py` when the user is
# actually online past the configured hour. Personality-flavored — a
# 장난꾸러기's morning hello is very different from a 차분한's.

MORNING_ARRIVAL: Dict[Personality, List[str]] = {
    Personality.PLAYFUL: [
        "왔다왔다~ ☆ 오늘은 뭐 할 거야?",
        "히히 ✨ 출근 도장 찍었네!",
        "에헴! 오늘도 같이 노닥거리자~",
    ],
    Personality.CALM: [
        "좋은 아침이야. 차분히 시작해보자.",
        "오늘도 천천히, 너의 페이스로.",
        "어서와. 조용한 하루이길.",
    ],
    Personality.BRAVE: [
        "와하하! 오늘도 출근이다! 💪",
        "준비됐다! 어떤 일이든 같이 가자!",
        "후훗 — 오늘은 또 어떤 도전이 기다리려나!",
    ],
    Personality.SHY: [
        "...좋은 아침... 이에요.",
        "안녕... 오늘도 잘 부탁해.",
        "...왔구나. 다행이야.",
    ],
    Personality.NAIVE: [
        "어! 어어! 왔다왔다! 헤헤 ☆",
        "헤헤 안녕~ 오늘도 같이!",
        "오! 좋은 아침 좋은 아침!",
    ],
    Personality.SMART: [
        "출근 확인. 오늘도 효율을 챙겨봐.",
        "음, 정시군. 좋은 시작이야.",
        "후훗 ✨ 오늘의 일정도 잘 부탁해.",
    ],
}

LUNCH: Dict[Personality, List[str]] = {
    Personality.PLAYFUL: [
        "점심시간이다아아 ☆ 뭐 먹을래?",
        "히히 ✨ 배고프지 않아? 가자가자!",
        "ㅋㅋ 시간 됐어 점심 점심!",
    ],
    Personality.CALM: [
        "12시야. 천천히 식사하자.",
        "점심시간이네. 잘 챙겨먹어.",
        "...밥 먹을 시간이야.",
    ],
    Personality.BRAVE: [
        "점심이다! 든든하게 먹고 와! 🍱",
        "와하하 충전 시간이야! 잘 먹고 와!",
        "에너지 보충 타임! 가자!",
    ],
    Personality.SHY: [
        "...점심시간이에요. 꼭 챙겨먹어요.",
        "...밥 거르지 말고... 응?",
        "점심... 같이 먹는 것 같은 기분으로...",
    ],
    Personality.NAIVE: [
        "냠냠 시간이다! 헤헤 ☆ 맛있는 거 먹어!",
        "와아 점심! 점심! 가자!",
        "뭐 먹을 거야? 응? 응?",
    ],
    Personality.SMART: [
        "12시 정각. 식사를 권장해.",
        "효율을 위해서는 점심도 중요해. 가봐.",
        "흠흠, 식사 시간이군. 챙겨먹어.",
    ],
}

EVENING_FAREWELL: Dict[Personality, List[str]] = {
    Personality.PLAYFUL: [
        "퇴근이다아아 ☆ 오늘도 수고했어!",
        "히히 ✨ 내일 봐~ 잘 가!",
        "ㅋㅋㅋ 끝났네 끝났어! 잘 쉬어!",
    ],
    Personality.CALM: [
        "오늘 하루 수고했어. 푹 쉬어.",
        "퇴근 시간이네. 천천히 정리하자.",
        "...수고했어. 내일 또 봐.",
    ],
    Personality.BRAVE: [
        "오늘도 잘 싸웠다! 💪 내일도 화이팅!",
        "와하하 퇴근이다! 잘 쉬고 내일 보자!",
        "오늘 하루도 훌륭했어. 푹 쉬어!",
    ],
    Personality.SHY: [
        "...수고했어요. 푹 쉬세요.",
        "...오늘도 고마웠어. 잘 가...",
        "...내일도, 와줘.",
    ],
    Personality.NAIVE: [
        "끝났어! 끝났어! 헤헤 잘 가~",
        "내일 또 보자! 응? 응? ☆",
        "와아 퇴근! 잘 자!",
    ],
    Personality.SMART: [
        "근무 종료. 충분한 휴식을 권장해.",
        "후훗 ✨ 오늘의 일과 완료. 잘 쉬어.",
        "퇴근 확인. 내일도 효율적으로.",
    ],
}


# ---- absence buckets (welcome-back) ----
#
# `pick_welcome_back(personality, absence_hours)` returns a line graded
# by how long the user was gone. Used at app startup when the buddy
# realizes the user has been away for a while.

class AbsenceBucket(Enum):
    SHORT = "short"     # 24h – 3d
    MEDIUM = "medium"   # 3d – 7d
    LONG = "long"       # 7d+


def absence_bucket(hours: float) -> Optional[AbsenceBucket]:
    """Map raw hours to a bucket. Returns None for < 24h (no welcome-back
    needed; the daily greeting flow covers normal returns)."""
    from .config import (
        ABSENCE_LONG_HOURS,
        ABSENCE_MEDIUM_HOURS,
        ABSENCE_SHORT_HOURS,
    )
    if hours < ABSENCE_SHORT_HOURS:
        return None
    if hours < ABSENCE_MEDIUM_HOURS:
        return AbsenceBucket.SHORT
    if hours < ABSENCE_LONG_HOURS:
        return AbsenceBucket.MEDIUM
    return AbsenceBucket.LONG


WELCOME_BACK: Dict[Personality, Dict[AbsenceBucket, List[str]]] = {
    Personality.PLAYFUL: {
        AbsenceBucket.SHORT: [
            "오! 오랜만이네 ㅋㅋ 어디 갔다 왔어?",
            "히히 ☆ 한참 안 보이더니!",
            "에이~ 오랜만이야 ㅋㅋ",
        ],
        AbsenceBucket.MEDIUM: [
            "어어! 며칠 만이야! 어디 갔었어?!",
            "ㅋㅋㅋ 정말 오랜만이네! 보고 싶었어!",
            "야아~ 며칠을 안 봤어! 심심했다고!",
        ],
        AbsenceBucket.LONG: [
            "헐... 진짜 한참 만이야! 어디 갔다 온 거야!",
            "ㅠㅠ 너무 오랜만이잖아! 보고 싶었어!",
            "야!! 일주일도 넘었어!! 어디 갔었어!!",
        ],
    },
    Personality.CALM: {
        AbsenceBucket.SHORT: [
            "...오랜만이야. 잘 지냈어?",
            "다시 만나서 다행이야.",
            "...많이 기다렸어.",
        ],
        AbsenceBucket.MEDIUM: [
            "며칠 만이네. 별일 없었어?",
            "...오랫동안 못 봤어. 걱정했어.",
            "다시 만나서 정말 다행이야.",
        ],
        AbsenceBucket.LONG: [
            "...한참 만이야. 정말 보고 싶었어.",
            "오랜 시간이었어. 무사해서 다행이야.",
            "...너무 오래 못 봤어. 마음 한구석이 비어있었어.",
        ],
    },
    Personality.BRAVE: {
        AbsenceBucket.SHORT: [
            "오랜만이다! 어디 갔다 왔어?",
            "와하하! 다시 만났네! 반갑다!",
            "후훗, 오랜만이야!",
        ],
        AbsenceBucket.MEDIUM: [
            "며칠 만이군! 임무 다녀온 거야?",
            "와! 한참 만이다! 컨디션 어때?",
            "그동안 어디 다녀왔어? 무사한 거지?",
        ],
        AbsenceBucket.LONG: [
            "이렇게나 오래! 걱정했잖아! 무사한 거지?",
            "한참 만이다! 다시 만나서 정말 다행이야!",
            "와하하 — 진짜 오랜만이야! 보고 싶었어!",
        ],
    },
    Personality.SHY: {
        AbsenceBucket.SHORT: [
            "...아, 오랜만이에요...",
            "...많이 기다렸어요.",
            "...다시 만나서... 다행이야.",
        ],
        AbsenceBucket.MEDIUM: [
            "...며칠 동안... 안 보였어요.",
            "...보고 싶었어. 정말로.",
            "...걱정했어요... 무사해서 다행...",
        ],
        AbsenceBucket.LONG: [
            "...너무 오래 안 보이셔서... 걱정했어요...",
            "...진짜 보고 싶었어요. 많이...",
            "...오랜만이야... 정말 정말 오랜만...",
        ],
    },
    Personality.NAIVE: {
        AbsenceBucket.SHORT: [
            "어어! 왔다왔다! 어디 갔었어?!",
            "히히 오랜만이다아!",
            "헤헤 ☆ 보고 싶었어!",
        ],
        AbsenceBucket.MEDIUM: [
            "와아아! 며칠 만이야! 어디 갔어!",
            "헤헤 오랜만 오랜만! 보고 싶었어!",
            "어! 어디 갔었어 어디 갔었어?!",
        ],
        AbsenceBucket.LONG: [
            "꺄아아! 진짜 오랜만이야! 어디 갔던 거야!!",
            "ㅠㅠ 너무너무 보고 싶었어! 다신 가지 마!",
            "와아아아 ✨ 보고 싶었어 정말! 어디 갔었던 거야!!",
        ],
    },
    Personality.SMART: {
        AbsenceBucket.SHORT: [
            "음, 오랜만이군. 다시 활성 상태로 환영해.",
            "흠. 24시간 이상 부재였어. 잘 다녀왔어?",
            "후훗 — 다시 만나서 반갑다.",
        ],
        AbsenceBucket.MEDIUM: [
            "흠흠, 며칠 만의 재회군. 데이터가 그리웠어.",
            "...3일 넘게 안 보이더라. 무탈했나?",
            "꽤 긴 부재였어. 보고 싶었던 게 인정돼.",
        ],
        AbsenceBucket.LONG: [
            "...일주일 넘게 비활성. 변수가 너무 많이 쌓였어.",
            "흠. 통계적으로 비정상적인 부재. ...걱정했어.",
            "후훗... 이론적으로 사랑이 그리웠다고밖에는.",
        ],
    },
}


def pick_morning(personality: Personality) -> str:
    return random.choice(MORNING_ARRIVAL[personality])


def pick_lunch(personality: Personality) -> str:
    return random.choice(LUNCH[personality])


def pick_farewell(personality: Personality) -> str:
    return random.choice(EVENING_FAREWELL[personality])


def pick_welcome_back(personality: Personality,
                      absence_hours: float) -> Optional[str]:
    """Return a welcome-back line if absence was 24h+, else None so the
    caller can fall back to a normal daily greeting."""
    bucket = absence_bucket(absence_hours)
    if bucket is None:
        return None
    return random.choice(WELCOME_BACK[personality][bucket])


# ---- chatter intervals (vary by tier) ----
# Affectionate buddy talks much more often; awkward buddy sits in silence.
CHATTER_INTERVALS_S: Dict[Tier, tuple] = {
    Tier.AWKWARD:      (7 * 60, 20 * 60),
    Tier.BUDDING:      (5 * 60, 15 * 60),
    Tier.FRIENDLY:     (4 * 60, 12 * 60),
    Tier.AFFECTIONATE: (2 * 60,  8 * 60),
}


def next_chatter_interval(friendship: int) -> int:
    lo, hi = CHATTER_INTERVALS_S[tier_for(friendship)]
    return random.randint(lo, hi)


# ---- pick helpers ----

def pick(bank: Dict[Tier, List[str]], friendship: int) -> str:
    """Random message from the bank for this friendship tier. Used for
    action banks (FEED/PLAY/TRAIN/PET/GREETING) which don't vary by
    personality."""
    return random.choice(bank[tier_for(friendship)])


# A line the buddy says right before being sent away (보내기 confirm).
FAREWELL: List[str] = [
    "그동안 즐거웠어… 새 친구한테도 잘 보일게!",
    "엥? 나… 어디 가는 거야?",
    "새로운 모험이라니, 살짝 설레는걸?",
    "잘 지내! 가끔 내 생각도 해줘.",
    "고마웠어. 너랑 보낸 시간 잊지 않을게.",
    "정든 자리를 떠나려니 조금 아쉽다…",
    "또 만날 수 있겠지? 그때까지 안녕!",
    "새 친구도 나만큼 아껴줄까…?",
]


def pick_farewell() -> str:
    """A random goodbye line for the 보내기 (send) confirmation."""
    return random.choice(FAREWELL)


# A 수집광 buddy's line when it reels in a dropped item.
COLLECTOR_LINES: List[str] = [
    "내가 주워올게! 🧲",
    "이건 내 거~ 슈웅!",
    "주섬주섬… 또 하나 겟!",
    "수집은 내 취미라구!",
    "놓칠 줄 알고? 휙!",
]


def pick_collector() -> str:
    return random.choice(COLLECTOR_LINES)


# A 명포수(catcher) buddy's line when it auto-throws a ball at a wild.
CATCHER_LINES: List[str] = [
    "저 녀석, 내가 잡는다! 🎯",
    "몬스터볼, 가랏!",
    "도망 못 가게 해줄게!",
    "이건 내 사냥감이야!",
]


def pick_catcher() -> str:
    return random.choice(CATCHER_LINES)


# Per-food / per-toy flavor lines — the buddy reacts differently to each.
FOOD_LINES: Dict[str, List[str]] = {
    "food.apple":   ["아삭아삭 사과 맛있다!", "사과는 언제나 옳아 🍎", "한 입 더 줄래?"],
    "food.berry":   ["달콤한 딸기 최고!", "딸기 더 없어? 🍓", "새콤달콤 좋아!"],
    "food.cake":    ["케이크라니, 오늘 무슨 날이야? 🍰", "달다 달아~", "특별한 기분이야!"],
    "food.cookie":  ["바삭한 과자 좋아! 🍪", "과자 부스러기까지 싹싹", "이거 중독성 있어!"],
    "food.pizza":   ["피자다! 한 조각 더! 🍕", "치즈 쭉~ 늘어나!"],
    "food.burger":  ["햄버거 크게 한 입! 🍔", "패티 육즙 최고!"],
    "food.fries":   ["감자튀김 바삭바삭! 🍟", "케첩 찍어 먹을래!"],
    "food.hotdog":  ["핫도그 좋아! 🌭", "한 입에 쏙!"],
    "food.egg":     ["계란프라이 노른자 톡! 🍳", "고소해~"],
    "food.pancake": ["팬케이크 폭신폭신! 🥞", "시럽 듬뿍!"],
    "food.salad":   ["샐러드라니 건강해지는 기분 🥗", "아삭아삭 채소!"],
    "food.kebab":   ["케밥 푸짐하다! 🥙", "이것저것 다 들었네!"],
    "food.steak":   ["스테이크라니 호강이야 🥩", "육즙이 팡!"],
    "food.ramen":   ["라멘 후루룩! 🍜", "국물까지 싹!"],
    "food.sushi":   ["초밥 신선해! 🍣", "한 점 더 줄래?"],
    "food.fondue":  ["퐁뒤 찍어 먹는 재미! 🫕", "치즈 폭포다!"],
    "food.dango":   ["경단 쫄깃쫄깃! 🍡", "달달해~"],
    "food.grapes":  ["포도 톡톡 터져! 🍇", "새콤달콤!"],
    "food.chestnut":["군밤 고소해! 🌰", "따끈따끈~"],
    "food.pepper":  ["피망도 잘 먹지! 🫑", "아삭한 맛!"],
    "food.olive":   ["올리브 짭짤해 🫒", "어른의 맛인가?"],
    "food.chili":   ["고추 맵지만 좋아! 🌶️", "앗 매워! 그래도 또!"],
}
_FOOD_DEFAULT = ["냠냠, 맛있어!", "잘 먹었어!", "배불러~ 고마워!"]

TOY_LINES: Dict[str, List[str]] = {
    "toy.ball":        ["공놀이 가자! 🎾", "데굴데굴 신난다", "또 던져줘!"],
    "toy.kite":        ["연 날리자! 🪁", "바람 타고 훨훨~", "하늘 높이 올라간다!"],
    "toy.bell":        ["딸랑딸랑 방울 소리 좋아 🔔", "이 소리 좋은데?"],
    "toy.firecracker": ["펑! 폭죽 신난다 🧨", "반짝반짝 터진다!"],
    "toy.palette":     ["그림 그리자! 🎨", "알록달록 예뻐!"],
    "toy.baseball":    ["야구공 던져줘! ⚾", "홈런 칠 거야!"],
    "toy.softball":    ["소프트볼 받기 연습! 🥎", "데구르르~"],
    "toy.basketball":  ["농구공 슛! 🏀", "드리블 드리블~"],
    "toy.volleyball":  ["배구공 토스! 🏐", "스파이크!"],
    "toy.football":    ["럭비공 잡았다! 🏈", "터치다운!"],
    "toy.soccer":      ["축구공 차자! ⚽", "골인!"],
    "toy.lipstick":    ["립스틱으로 꾸며볼까? 💄", "예뻐졌지?"],
    "toy.pingpong":    ["탁구 핑퐁핑퐁! 🏓", "랠리 가자!"],
    "toy.dice":        ["주사위 굴려! 🎲", "6 나와라!"],
    "toy.teddy":       ["곰인형 폭신해 🧸", "꼬옥 안아줘!"],
    "toy.wand":        ["요술봉 휘둘러! 🪄", "뿅! 마법이다!"],
    "toy.cards":       ["화투 한 판? 🎴", "패가 좋은데?"],
    "toy.yoyo":        ["요요 위아래로! 🪀", "묘기 부려볼까?"],
    "toy.horn":        ["빠밤~ 나팔 분다 📯", "소리 우렁차!"],
    "toy.flute":       ["피리 삐리리~ 🪈", "노래 불러볼까?"],
    "toy.maracas":     ["마라카스 흔들흔들! 🪇", "차차차!"],
    "toy.violin":      ["바이올린 켜볼까? 🎻", "선율이 아름다워~"],
    "toy.piano":       ["피아노 도레미! 🎹", "연주 들려줄게!"],
    "toy.crayon":      ["크레용으로 쓱쓱! 🖍️", "낙서 재밌어!"],
    "toy.bubble":      ["비눗방울 둥둥~ 🫧", "팡팡 터뜨리자!"],
}
_TOY_DEFAULT = ["신난다! 같이 놀자!", "재밌어!", "더 놀고 싶어!"]


def pick_food_line(item_key: str) -> str:
    return random.choice(FOOD_LINES.get(item_key, _FOOD_DEFAULT))


def pick_toy_line(item_key: str) -> str:
    return random.choice(TOY_LINES.get(item_key, _TOY_DEFAULT))


# Probability of drawing from the hidden bond-max pool when the buddy is
# at friendship 100. Lower than 1.0 so regular AFFECTIONATE chatter still
# appears occasionally — keeps variety.
BOND_MAX_PROBABILITY = 0.40


def pick_chatter(personality: Personality, friendship: int) -> str:
    """Pick an ambient chatter line tailored to the buddy's personality.
    At friendship 100, occasionally pull a hidden bond-max line instead."""
    tier = tier_for(friendship)
    if friendship >= 100 and random.random() < BOND_MAX_PROBABILITY:
        pool = BOND_MAX_LINES.get(personality)
        if pool:
            return random.choice(pool)
    bank = CHATTER_BY_PERSONALITY.get(personality)
    if bank is None:
        # No bank for this personality — should never happen, but fall back
        # to a generic chatter line so the engine doesn't crash.
        return "..."
    return random.choice(bank[tier])
