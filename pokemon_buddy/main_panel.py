"""Single host dialog for all four tabs (bag / inventory / dex / reminders).

NavBar at the top, QStackedWidget below. Clicking a nav tab swaps the
visible page; the window itself stays open. Each tab's content widget
(`*Panel`) is lazy-built on first activation, then cached for instant
subsequent switches.

Functional signals (e.g. `set_as_buddy` from BagPanel) are forwarded
upward via this host so `BuddyApp` doesn't need to know which tab is open."""

from __future__ import annotations

from typing import Dict

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .bag_dialog import BagPanel
from .config import DIALOG_H, DIALOG_W
from .daily_schedule_dialog import DailySchedulePanel
from .dex_dialog import DexPanel
from .inventory_dialog import InventoryPanel
from .nav_bar import (
    NAV_DEX,
    NAV_INVENTORY,
    NAV_POKEMON,
    NAV_REMINDERS,
    NAV_SCHEDULE,
    NavBar,
)
from .reminder_dialog import ReminderPanel
from .state import Store


class MainPanel(QDialog):
    """One window, four tabs. Cheaper than recreating a QDialog per tab and
    keeps the user oriented (no popup-then-disappear ceremony)."""

    set_as_buddy = Signal(int)           # bag_id picked in BagPanel
    bag_changed = Signal()                # rename / release in BagPanel
    reminders_saved = Signal()            # ReminderPanel Save clicked
    schedule_saved = Signal()             # DailySchedulePanel Save clicked
    use_item_requested = Signal(str)     # SPECIAL item 사용 clicked
    show_detail = Signal(int)            # bag_id — open PokemonDetailDialog

    def __init__(self, store: Store, sprite_style: str, active_bag_id: int,
                 initial_tab: str = NAV_POKEMON,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pokemon Buddy")
        self.setMinimumSize(DIALOG_W, DIALOG_H)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        self.store = store
        self.sprite_style = sprite_style
        self.active_bag_id = active_bag_id

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        self.nav = NavBar(current=initial_tab)
        self.nav.nav.connect(self._switch_tab)
        root.addWidget(self.nav)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, stretch=1)

        self._panels: Dict[str, QWidget] = {}
        self._switch_tab(initial_tab)

    # ---- API ----
    def update_active_bag_id(self, bag_id: int) -> None:
        """Called after a buddy swap so the bag panel highlight stays right."""
        self.active_bag_id = bag_id
        bag = self._panels.get(NAV_POKEMON)
        if isinstance(bag, BagPanel):
            bag.update_active(bag_id)

    def refresh_bag(self) -> None:
        bag = self._panels.get(NAV_POKEMON)
        if isinstance(bag, BagPanel):
            bag.refresh()

    def refresh_inventory(self) -> None:
        inv = self._panels.get(NAV_INVENTORY)
        if isinstance(inv, InventoryPanel):
            inv.refresh()

    def refresh_dex(self) -> None:
        """Drop the cached dex panel so the next view rebuilds. DexPanel
        reads the registry at construction time so a simple `refresh()`
        method would require restructuring — cache invalidation is enough."""
        old = self._panels.pop(NAV_DEX, None)
        if old is None:
            return
        self.stack.removeWidget(old)
        old.deleteLater()

    # ---- tab routing ----
    def _switch_tab(self, key: str) -> None:
        panel = self._build_panel(key)
        self.stack.setCurrentWidget(panel)
        self.nav.set_current(key)

    def _build_panel(self, key: str) -> QWidget:
        if key in self._panels:
            return self._panels[key]
        if key == NAV_POKEMON:
            panel = BagPanel(self.store, self.sprite_style, self.active_bag_id)
            panel.set_as_buddy.connect(self._on_bag_set_active)
            panel.bag_changed.connect(self.bag_changed)
            panel.show_detail.connect(self.show_detail)
        elif key == NAV_INVENTORY:
            panel = InventoryPanel(self.store)
            panel.use_item_requested.connect(self.use_item_requested)
        elif key == NAV_DEX:
            panel = DexPanel(self.store, self.sprite_style)
        elif key == NAV_REMINDERS:
            panel = ReminderPanel(self.store)
            panel.saved.connect(self.reminders_saved)
        elif key == NAV_SCHEDULE:
            panel = DailySchedulePanel(self.store)
            panel.saved.connect(self.schedule_saved)
        else:
            raise ValueError(f"unknown nav key: {key}")
        self._panels[key] = panel
        self.stack.addWidget(panel)
        return panel

    def _on_bag_set_active(self, bag_id: int) -> None:
        # Reflect the new active locally and forward up to the app.
        self.active_bag_id = bag_id
        bag = self._panels.get(NAV_POKEMON)
        if isinstance(bag, BagPanel):
            bag.update_active(bag_id)
        self.set_as_buddy.emit(bag_id)

    # ---- teardown ----
    def closeEvent(self, ev) -> None:  # noqa: N802
        for panel in self._panels.values():
            if hasattr(panel, "cleanup"):
                panel.cleanup()
        super().closeEvent(ev)
