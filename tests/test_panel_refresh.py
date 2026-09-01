"""내 포켓몬 탭 갱신 — the cards must not keep showing pre-action numbers.

Every user action that moves EXP / 레벨 / 친밀도 / 종족 has to repopulate
the bag panel. Actions used to refresh only the inventory tab, so feeding
or eating a 이상한사탕 left the card stale until it was rebuilt."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from pokemon_buddy.app import BuddyApp


class _PanelSpy:
    """Stands in for MainPanel — records which tabs got repainted."""

    def __init__(self) -> None:
        self.bag = 0
        self.dex = 0
        self.inventory = 0

    def refresh_bag(self) -> None:
        self.bag += 1

    def refresh_dex(self) -> None:
        self.dex += 1

    def refresh_inventory(self) -> None:
        self.inventory += 1


def _app_with(panel):
    """`_refresh_after_buddy_change` only touches `self._main_panel`, so we
    can exercise it without standing up a whole BuddyApp (tray icon, pet
    windows, timers)."""
    return SimpleNamespace(_main_panel=panel)


def test_buddy_change_repaints_bag_only():
    panel = _PanelSpy()
    BuddyApp._refresh_after_buddy_change(_app_with(panel))
    assert panel.bag == 1
    # 도감 is untouched unless the species actually changed.
    assert panel.dex == 0


def test_evolution_repaints_bag_and_dex():
    panel = _PanelSpy()
    BuddyApp._refresh_after_buddy_change(_app_with(panel), dex_changed=True)
    assert panel.bag == 1
    assert panel.dex == 1


def test_refresh_is_safe_with_no_panel_open():
    # Nothing open → must not raise; the vast majority of actions happen
    # with the main window closed.
    BuddyApp._refresh_after_buddy_change(SimpleNamespace(_main_panel=None))
    BuddyApp._refresh_after_buddy_change(SimpleNamespace())


# ---- the real widget actually repaints ----

@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _exp_labels(widget):
    from PySide6.QtWidgets import QLabel
    return [w.text() for w in widget.findChildren(QLabel) if "EXP " in w.text()]


def test_refresh_bag_picks_up_new_exp(qapp, store, temp_assets, no_network):
    from pokemon_buddy.main_panel import MainPanel
    from pokemon_buddy.nav_bar import NAV_POKEMON

    buddy = store.list_bag()[0]
    panel = MainPanel(store, "showdown", buddy.bag_id, initial_tab=NAV_POKEMON)
    try:
        before = _exp_labels(panel)
        assert before, "bag card should print an EXP line"

        gained, _ = store.gain_exp_detailed(buddy, 70)
        assert gained == 70
        panel.refresh_bag()

        after = _exp_labels(panel)
        assert after != before, "refresh_bag() must repaint the EXP numbers"
        assert any(f"EXP {buddy.exp}/" in t for t in after)
    finally:
        panel.close()
