"""Small UI-behavior tweaks: farewell lines + per-kind drop sizing."""

from __future__ import annotations

from pokemon_buddy import messages
from pokemon_buddy.item_drop import drop_size_for
from pokemon_buddy.config import ITEM_DROP_SIZE_PX, ITEM_DROP_SIZE_SMALL_PX
from pokemon_buddy.items import ItemKind


def test_pick_farewell_returns_known_line():
    line = messages.pick_farewell()
    assert isinstance(line, str) and line
    assert line in messages.FAREWELL


def test_farewell_bank_nonempty():
    assert len(messages.FAREWELL) >= 3


def test_drop_size_small_for_food_toy_ball():
    for kind in (ItemKind.FOOD, ItemKind.TOY, ItemKind.POKEBALL):
        assert drop_size_for(kind) == ITEM_DROP_SIZE_SMALL_PX
    # special + skill keep the larger size
    for kind in (ItemKind.SPECIAL, ItemKind.SKILL):
        assert drop_size_for(kind) == ITEM_DROP_SIZE_PX
    assert ITEM_DROP_SIZE_SMALL_PX < ITEM_DROP_SIZE_PX


def test_collector_and_catcher_lines_nonempty():
    assert messages.pick_collector() in messages.COLLECTOR_LINES
    assert messages.pick_catcher() in messages.CATCHER_LINES
    assert messages.COLLECTOR_LINES and messages.CATCHER_LINES


def test_random_available_of_kind(store, temp_assets):
    store.add_item("food.cake", 1)
    keys = {store.random_available_of_kind("food") for _ in range(30)}
    # only owned foods come back, and more than one variety can appear
    assert keys and all(k.startswith("food.") for k in keys)
    for k in keys:
        assert store.get_item_count(k) > 0
    # a kind with nothing owned → None (no special items by default)
    assert store.random_available_of_kind("special") is None


def test_food_toy_flavor_lines():
    assert messages.pick_food_line("food.apple") in messages.FOOD_LINES["food.apple"]
    assert messages.pick_toy_line("toy.ball") in messages.TOY_LINES["toy.ball"]
    # unknown key falls back to a generic line (non-empty)
    assert messages.pick_food_line("food.unknown")
    assert messages.pick_toy_line("toy.unknown")


def test_catcher_skill_registered():
    from pokemon_buddy import skills
    sk = skills.find(skills.SKILL_CATCHER)
    assert sk is not None and sk.name == "명포수"
    # learnable/sendable via its teaching scroll
    assert skills.skill_for_item("skill.catcher") is sk
    from pokemon_buddy.items import find as find_item
    assert find_item("skill.catcher") is not None


def test_hearts_bar_is_five_slots_of_matching_emoji(store):
    """친밀도 게이지 — one definition, five slots, both halves colour emoji.

    The heart glyphs used to be written out at five separate call sites and
    had already drifted: some used ❤️ (emoji) with ♡ (a thin text outline),
    others plain ❤. `Buddy.hearts_bar` is now the only source."""
    from pokemon_buddy.config import HEART_EMPTY, HEART_FULL

    b = store.add_to_bag(25, is_rare=False)
    for friendship, filled in ((0, 0), (19, 0), (20, 1), (55, 2),
                               (80, 4), (99, 4), (100, 5)):
        b.friendship = friendship
        store.save_active_buddy(b)
        bar = b.hearts_bar
        assert bar.count(HEART_FULL) == filled, f"친밀도 {friendship}"
        assert bar.count(HEART_EMPTY) == 5 - filled, f"친밀도 {friendship}"


def test_heart_glyphs_are_a_matched_pair():
    """Both halves must be emoji presentation, or the gauge renders as a
    mix of a coloured heart and a hairline outline."""
    from pokemon_buddy.config import HEART_EMPTY, HEART_FULL

    assert HEART_FULL and HEART_EMPTY
    assert HEART_FULL != HEART_EMPTY
    # ❤ needs U+FE0F to render as emoji rather than the text dingbat.
    if "\u2764" in HEART_FULL:
        assert "\ufe0f" in HEART_FULL, "❤ without VS16 renders as text glyph"
    # 🤍 is already emoji-default (U+1F90D), no selector needed.
    assert HEART_EMPTY != "\u2661", "♡ is a text outline, not an emoji"


def test_dex_grid_fits_inside_the_window():
    """도감 4열이 창 안에 들어와야 한다.

    The card width is derived from DIALOG_W, and the derivation used to
    forget the vertical scrollbar — the dex always has one (151+ entries),
    so the rightmost column was clipped by ~10px. Guard the arithmetic so
    a future width tweak can't quietly re-break it."""
    from pokemon_buddy import dex_dialog as d

    used = d.COLS * d.CARD_W + (d.COLS - 1) * d.GRID_SPACING
    assert used <= d._CONTENT_W, (
        f"4열이 {used}px를 쓰는데 {d._CONTENT_W}px만 있음 — 오른쪽이 잘림"
    )
    # And the content budget must itself leave room for the scrollbar.
    from pokemon_buddy.config import DIALOG_W
    assert d._CONTENT_W + d._SCROLLBAR_W <= DIALOG_W
    assert d.CARD_W > 0


def test_saved_window_positions_can_be_cleared(store):
    """포켓몬 자리 정렬 — the saved spot has to actually go, or the default
    row placement never gets a chance to run."""
    a = store.add_to_bag(1, is_rare=False)
    b = store.add_to_bag(4, is_rare=False)
    for buddy in (a, b):
        store.set_meta(f"win_x_{buddy.bag_id}", "1234")
        store.set_meta(f"win_y_{buddy.bag_id}", "567")

    store.clear_window_position(a.bag_id)
    assert store.get_meta(f"win_x_{a.bag_id}") is None
    assert store.get_meta(f"win_y_{a.bag_id}") is None
    # …and only that one.
    assert store.get_meta(f"win_x_{b.bag_id}") == "1234"

    store.set_meta("onboarded", "1")            # an unrelated key
    removed = store.clear_all_window_positions()
    assert removed == 2
    assert store.get_meta(f"win_x_{b.bag_id}") is None
    assert store.get_meta("onboarded") == "1", "wiped an unrelated meta key"


def test_party_row_puts_slot_zero_leftmost():
    """대표(슬롯 0)가 제일 왼쪽, 마지막 슬롯이 화면 오른쪽 끝.

    Mirrors BuddyApp._layout_party_row: walk right→left accumulating each
    window's own width, so a 3x-scaled member pushes its neighbours out
    instead of overlapping them."""
    from pokemon_buddy.config import PARTY_SLOT_GAP_PX, PET_SCREEN_MARGIN

    screen_right, screen_bottom = 2193, 1185
    widths = [93, 93, 140]        # slot 2 is a 3x-scaled buddy

    right = screen_right - PET_SCREEN_MARGIN
    bottom = screen_bottom - PET_SCREEN_MARGIN
    placed = {}
    for slot in reversed(range(len(widths))):
        w = widths[slot]
        placed[slot] = (right - w, bottom - w)
        right -= w + PARTY_SLOT_GAP_PX

    xs = [placed[s][0] for s in range(len(widths))]
    # Slot 0 leftmost, ascending to the right.
    assert xs == sorted(xs), f"슬롯 0이 제일 왼쪽이어야 함: {xs}"
    # Last slot hugs the right edge.
    assert xs[-1] + widths[-1] == screen_right - PET_SCREEN_MARGIN
    # Nobody overlaps — including the oversized one.
    for i in range(len(widths) - 1):
        gap = xs[i + 1] - (xs[i] + widths[i])
        assert gap == PARTY_SLOT_GAP_PX, f"슬롯 {i}-{i+1} 간격 {gap}"
    # Bottoms line up.
    assert len({placed[s][1] + widths[s] for s in range(len(widths))}) == 1


def test_prune_keeps_only_party_positions(store):
    """현재 버디만 위치를 기억한다 — bag-only buddies don't need coordinates,
    and released ones left rows behind forever (10 of 17 saved positions
    once belonged to Pokemon that no longer existed)."""
    in_party = store.add_to_bag(1, is_rare=False)
    benched = store.add_to_bag(4, is_rare=False)
    for b in (in_party, benched):
        store.set_meta(f"win_x_{b.bag_id}", "100")
        store.set_meta(f"win_y_{b.bag_id}", "200")
    store.set_meta("win_x_999999", "1")      # long-released buddy
    store.set_meta("win_y_999999", "2")

    removed = store.prune_buddy_meta([in_party.bag_id])
    assert removed == 4                       # benched pair + orphan pair
    assert store.get_meta(f"win_x_{in_party.bag_id}") == "100"
    assert store.get_meta(f"win_y_{in_party.bag_id}") == "200"
    assert store.get_meta(f"win_x_{benched.bag_id}") is None
    assert store.get_meta("win_x_999999") is None


def test_prune_keeps_evolution_flags_for_owned_buddies(store):
    """evo_declined_ lives as long as the bag entry — being benched must
    not make the evolution prompt start nagging again."""
    benched = store.add_to_bag(1, is_rare=False)
    store.set_evolution_declined(benched.bag_id, 2)
    store.set_meta("evo_declined_999999", "5")   # released buddy

    store.prune_buddy_meta([])                   # nobody in the party
    assert store.is_evolution_declined(benched.bag_id, 2) is True
    assert store.get_meta("evo_declined_999999") is None


def test_prune_leaves_unrelated_meta_alone(store):
    store.set_meta("adventurer_name", "소온")
    store.set_meta("sprite_style", "showdown")
    store.set_meta("win_x_notanumber", "keep-me")
    store.prune_buddy_meta([])
    assert store.get_meta("adventurer_name") == "소온"
    assert store.get_meta("sprite_style") == "showdown"
    assert store.get_meta("win_x_notanumber") == "keep-me"


# ---- 색상 테마 ----

def test_every_theme_is_complete_and_distinct():
    from pokemon_buddy import theme
    keys = [k for k, _ in theme.choices()]
    assert set(keys) == set(theme.THEMES)
    assert len(keys) == 4
    primaries = set()
    for k in keys:
        t = theme.THEMES[k]
        for field in (t.primary, t.primary_dark, t.primary_light,
                      t.on_primary, t.tint, t.tint_soft):
            assert field.startswith("#") and len(field) == 7, f"{k}: {field}"
        assert len(t.rgb) == 3 and all(0 <= c <= 255 for c in t.rgb)
        assert t.label
        primaries.add(t.primary)
    assert len(primaries) == 4, "테마마다 포인트 컬러가 달라야 함"


def test_theme_text_is_readable_on_every_surface():
    """밝은 파스텔 위에는 흰 글자가 안 읽힌다.

    The palettes are the starter hue at ~30% white, so every primary is a
    bright surface — each theme therefore pairs it with a deep same-hue
    `on_primary` instead of white. `primary_light` carries the same text
    (the 파티 badge uses that pairing), so check both."""
    from pokemon_buddy import theme

    def luminance(hex_color):
        r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
        f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

    def contrast(a, b):
        l1, l2 = sorted((luminance(a), luminance(b)))
        return (l2 + 0.05) / (l1 + 0.05)

    for key, t in theme.THEMES.items():
        for surface, name in ((t.primary, "primary"),
                              (t.primary_dark, "primary_dark"),
                              (t.primary_light, "primary_light")):
            c = contrast(surface, t.on_primary)
            assert c >= 4.5, f"{key}.{name}: 대비 {c:.2f} — 글자가 안 읽힘"
        # White would fail on these bright surfaces — none may use it.
        assert t.on_primary != "#ffffff", f"{key}: 밝은 배경에 흰 글자"


def test_themes_are_bright_but_soft():
    """"은은하게" = 밝기는 유지하고 채도만 낮추기. Darkening was the wrong
    lever — it made the chrome dingy instead of soft."""
    import colorsys
    from pokemon_buddy import theme

    for key, t in theme.THEMES.items():
        r, g, b = (int(t.primary[i:i + 2], 16) / 255 for i in (1, 3, 5))
        _, sat, val = colorsys.rgb_to_hsv(r, g, b)
        assert val >= 0.75, f"{key}: 명도 {val:.0%} — 너무 어두움"
        assert sat <= 0.70, f"{key}: 채도 {sat:.0%} — 너무 쨍함"


def test_theme_selection_round_trips():
    from pokemon_buddy import theme
    before = theme.current().key
    try:
        for key in theme.THEMES:
            t = theme.set_current(key)
            assert t.key == key
            assert theme.primary() == t.primary
            assert theme.on_primary() == t.on_primary
        # Unknown / missing keys fall back instead of blowing up.
        assert theme.set_current("nonsense").key == theme.DEFAULT_THEME
        assert theme.set_current(None).key == theme.DEFAULT_THEME
    finally:
        theme.set_current(before)


def test_primary_rgba_is_qt_shaped():
    """rgb must track primary — a stale tuple would tint hovers in the
    previous theme's colour."""
    from pokemon_buddy import theme
    before = theme.current().key
    try:
        for key, t in theme.THEMES.items():
            theme.set_current(key)
            r, g, b = (int(t.primary[i:i + 2], 16) for i in (1, 3, 5))
            assert t.rgb == (r, g, b), f"{key}: rgb가 primary와 불일치"
            assert theme.primary_rgba(30) == f"rgba({r}, {g}, {b}, 30)"
    finally:
        theme.set_current(before)


def test_bag_card_buttons_fit_inside_the_card():
    """버튼이 카드 밖으로 넘치면 다닥다닥 붙어 보인다.

    The four action buttons used to be one column: 4×18 + 3 gaps = 75px
    inside a 72px card. A 2×2 grid is the fix, so pin the arithmetic."""
    from pokemon_buddy.bag_dialog import (
        CARD_H, ICON_BTN_GAP, ICON_BTN_H, ICON_BTN_W,
    )
    card_padding = 3 + 3                       # outer layout top/bottom
    rows = 2                                   # 4 buttons in a 2×2 grid
    used = rows * ICON_BTN_H + (rows - 1) * ICON_BTN_GAP
    assert used <= CARD_H - card_padding, (
        f"버튼 {used}px > 가용 {CARD_H - card_padding}px — 카드를 넘침"
    )
    # And each button stays comfortably clickable.
    assert ICON_BTN_W >= 28 and ICON_BTN_H >= 24
