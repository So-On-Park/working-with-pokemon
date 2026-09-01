"""진화 팝업은 한 번만 — and the 진화시키기 button is the way back.

`_maybe_offer_evolution` used to re-ask on EVERY level-up once a buddy was
past its evolution level. With 이상한사탕 granting a level per candy that
turned into a modal popup per candy."""

from __future__ import annotations

import os

import pytest
from PySide6.QtCore import Qt

from pokemon_buddy.evolution import can_evolve


# 이상해씨(1) → 이상해풀(2) @ Lv.16
BULBASAUR, IVYSAUR, EVO_LEVEL = 1, 2, 16


def _bulbasaur_at(store, level):
    b = store.add_to_bag(BULBASAUR, is_rare=False, caught_with="pokeball.basic")
    b.level = level
    store.save_active_buddy(b)
    return b


def test_evolution_line_picks_the_right_particle():
    """"거북왕(으)로" reads like a form letter — the buddy is shouting."""
    from pokemon_buddy.messages import evolution_line, ro_particle
    # 받침 없음 / ㄹ 받침 → 로
    assert ro_particle("리자드") == "로"
    assert ro_particle("라이츄") == "로"
    assert ro_particle("이상해풀") == "로"
    # 그 외 받침 → 으로
    assert ro_particle("거북왕") == "으로"
    assert ro_particle("피죤") == "으로"
    # non-Hangul falls back safely
    assert ro_particle("Pikachu") == "로"
    assert ro_particle("") == "로"

    line = evolution_line("어니부기")
    assert line.startswith("어니부기로 진화!")
    assert "잘 부탁해" in line


def test_evolution_target_is_level_gated():
    assert can_evolve(BULBASAUR, EVO_LEVEL - 1) is None
    assert can_evolve(BULBASAUR, EVO_LEVEL) == IVYSAUR


def test_decline_is_remembered_per_target(store):
    b = _bulbasaur_at(store, EVO_LEVEL)
    assert store.is_evolution_declined(b.bag_id, IVYSAUR) is False

    store.set_evolution_declined(b.bag_id, IVYSAUR)
    assert store.is_evolution_declined(b.bag_id, IVYSAUR) is True

    # A *different* evolution still gets to ask once — declining 이상해풀
    # must not silence the 리자몽 stage later on.
    assert store.is_evolution_declined(b.bag_id, 3) is False


def test_decline_is_per_buddy(store):
    a = _bulbasaur_at(store, EVO_LEVEL)
    c = _bulbasaur_at(store, EVO_LEVEL)
    store.set_evolution_declined(a.bag_id, IVYSAUR)
    assert store.is_evolution_declined(a.bag_id, IVYSAUR) is True
    assert store.is_evolution_declined(c.bag_id, IVYSAUR) is False


def test_clearing_lets_it_ask_again(store):
    b = _bulbasaur_at(store, EVO_LEVEL)
    store.set_evolution_declined(b.bag_id, IVYSAUR)
    store.clear_evolution_declined(b.bag_id)
    assert store.is_evolution_declined(b.bag_id, IVYSAUR) is False


def test_repeated_level_ups_only_prompt_once(store):
    """The actual regression: candy-spam past the evolution level."""
    b = _bulbasaur_at(store, EVO_LEVEL)
    prompts = 0
    for _ in range(10):
        target = can_evolve(b.dex_id, b.level)
        if target is not None and not store.is_evolution_declined(
            b.bag_id, target
        ):
            prompts += 1
            store.set_evolution_declined(b.bag_id, target)  # user says "not yet"
        store.level_up_once(b)
    assert prompts == 1, "evolution must be offered once, not every level"
    assert b.level == EVO_LEVEL + 10


# ---- the button only appears when it can actually do something ----

@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _button_labels(widget):
    from PySide6.QtWidgets import QPushButton
    return [b.text() for b in widget.findChildren(QPushButton)]


def test_detail_dialog_offers_evolve_when_eligible(qapp, store, temp_assets,
                                                   no_network):
    from pokemon_buddy.pokemon_detail_dialog import PokemonDetailDialog
    b = _bulbasaur_at(store, EVO_LEVEL)
    dlg = PokemonDetailDialog(b, "showdown")
    try:
        assert "✨ 진화시키기" in _button_labels(dlg)
        assert dlg.evolve_requested is False
        dlg._on_evolve_clicked()
        assert dlg.evolve_requested is True
    finally:
        dlg.close()


def test_known_is_matched_per_variant(store):
    """도감은 이로치를 별도 항목으로 세니, 일반형을 안다고 이로치까지
    아는 것으로 치면 안 된다."""
    store.record_catch(IVYSAUR, "이상해풀", is_rare=False)
    assert store.get_dex_entry(IVYSAUR, is_rare=False) is not None
    # The shiny form is still unseen → must render as a silhouette.
    assert store.get_dex_entry(IVYSAUR, is_rare=True) is None


def test_silhouette_blacks_out_pixels_but_keeps_alpha(qapp):
    """도감에 없는 진화형은 검은 실루엣으로."""
    from PySide6.QtGui import QColor, QPainter, QPixmap
    from pokemon_buddy.evolution_dialog import silhouette

    pm = QPixmap(8, 8)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.fillRect(0, 0, 4, 8, QColor(255, 40, 40))   # left half opaque red
    p.end()

    out = silhouette(pm)
    img = out.toImage()
    left = img.pixelColor(1, 1)
    right = img.pixelColor(6, 1)
    # Opaque pixels go pure black…
    assert (left.red(), left.green(), left.blue()) == (0, 0, 0)
    assert left.alpha() == 255
    # …and transparent pixels stay transparent (it's a shape, not a box).
    assert right.alpha() == 0


def test_unknown_evolution_is_hidden_in_the_dialog(qapp, store, temp_assets,
                                                   no_network):
    from pokemon_buddy.evolution_dialog import EvolutionDialog, UNKNOWN_NAME
    dlg = EvolutionDialog("이상해씨", "이상해풀", None, None,
                          after_known=False)
    try:
        assert dlg.after_label_text == UNKNOWN_NAME
        # The name must not leak next to the silhouette.
        from PySide6.QtWidgets import QLabel
        texts = [w.text() for w in dlg.findChildren(QLabel)]
        assert "이상해풀" not in texts
        assert UNKNOWN_NAME in texts
    finally:
        dlg.close()


def test_known_evolution_shows_its_name(qapp, store, temp_assets, no_network):
    from pokemon_buddy.evolution_dialog import EvolutionDialog
    dlg = EvolutionDialog("이상해씨", "이상해풀", None, None,
                          after_known=True)
    try:
        assert dlg.after_label_text == "이상해풀"
    finally:
        dlg.close()


def test_detail_dialog_hides_evolve_when_not_eligible(qapp, store, temp_assets,
                                                      no_network):
    from pokemon_buddy.pokemon_detail_dialog import PokemonDetailDialog
    b = _bulbasaur_at(store, EVO_LEVEL - 1)
    dlg = PokemonDetailDialog(b, "showdown")
    try:
        assert "✨ 진화시키기" not in _button_labels(dlg)
    finally:
        dlg.close()


def test_clearing_removes_the_row_not_just_the_value(store):
    """빈 값으로 남기면 행은 그대로 쌓인다 — 진화한 버디마다 하나씩."""
    b = _bulbasaur_at(store, EVO_LEVEL)
    store.set_evolution_declined(b.bag_id, IVYSAUR)
    key = f"evo_declined_{b.bag_id}"
    assert store.get_meta(key) == str(IVYSAUR)

    store.clear_evolution_declined(b.bag_id)
    assert store.get_meta(key) is None, "행이 빈 값으로 남아 있음"
    rows = store.conn.execute(
        "SELECT COUNT(*) c FROM meta WHERE key=?", (key,)
    ).fetchone()
    assert rows["c"] == 0
