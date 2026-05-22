"""Application entry point — wires the window, tray, state, and game loop."""

from __future__ import annotations

import sys
import logging
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QIcon, QImageReader, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QInputDialog,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
)

from .animations import AnimationEngine
from .buddy_agent import BuddyAgent
from .config import (
    APP_ID,
    APP_NAME,
    BULK_DEX_RANGE,
    CATCH_EXP_REWARD,
    DEFAULT_SPRITE_STYLE,
    FRIENDSHIP_CATCH_WILD,
    FRIENDSHIP_FEED,
    FRIENDSHIP_LEVEL_UP,
    FRIENDSHIP_PET,
    FRIENDSHIP_PLAY,
    FRIENDSHIP_TRAIN,
    PASSIVE_EXP,
    PASSIVE_FRIENDSHIP_XP,
    PASSIVE_INTERVAL_S,
    PLAY_EXP,
    SPRITE_STYLES,
    TICK_MS,
    TRAIN_EXP,
)
from .buddy_popup import (
    ACTION_BAG,
    ACTION_DETAIL,
    ACTION_DEX,
    ACTION_FEED,
    ACTION_INVENTORY,
    ACTION_PLAY,
    ACTION_RENAME,
    ACTION_TRAIN,
    BuddyMenuPopup,
)
from .chatter import ChatterEngine
from . import custom_pokemon
from .custom_pokemon_dialog import CustomPokemonDialog
from .daily_schedule import DailyScheduleEngine
from .encounter import EncounterManager
from .evolution import can_evolve, get_stone_evolution_target
from .evolution_dialog import EvolutionDialog
from .item_drop import ItemDropManager
from .items import ITEMS, ItemKind, find as find_item
from .main_panel import MainPanel
from . import messages
from .pokemon_detail_dialog import PokemonDetailDialog
from .windows_state import is_screen_locked
from .nav_bar import NAV_DEX, NAV_INVENTORY, NAV_POKEMON, NAV_REMINDERS
from .pet_window import PetWindow, _placeholder_pixmap
from .pokemon_names import get_name
from .star_burst import StarBurst
from .reminders import ReminderScheduler
from .sprites import (
    get_buddy_sprite_with_fallback,
    get_model_sprite,
    prefetch_item_sprites,
    start_bulk_download,
)
from .state import Buddy, Reminder, Store

log = logging.getLogger(__name__)


def _tray_icon(buddy: Buddy, style: str) -> QIcon:
    """Build a static tray icon: first frame of the current style's GIF
    (rare variant if applicable), or a cached 3D PNG, or a placeholder blob."""
    sprite = get_buddy_sprite_with_fallback(style, buddy.dex_id, buddy.is_rare)
    if sprite is not None and str(sprite).lower().endswith(".gif"):
        reader = QImageReader(str(sprite))
        if reader.canRead():
            img = reader.read()
            if not img.isNull():
                return QIcon(QPixmap.fromImage(img))
    if sprite is not None and not str(sprite).lower().endswith(".gif"):
        pm = QPixmap(str(sprite))
        if not pm.isNull():
            return QIcon(pm)
    model = get_model_sprite(buddy.dex_id)
    if model is not None:
        pm = QPixmap(str(model))
        if not pm.isNull():
            return QIcon(pm)
    return QIcon(_placeholder_pixmap(64))


class _BulkDownloadAdapter(QObject):
    """Bridges sprite_bulk_download worker-thread callbacks to Qt signals
    on the GUI thread."""

    progress = Signal(int, int)
    finished = Signal(int, int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._stop = None

    def is_running(self) -> bool:
        return self._stop is not None and not self._stop.is_set()

    def start(self, style: str, dex_ids) -> bool:
        if self.is_running():
            return False
        self._stop = start_bulk_download(
            style,
            dex_ids,
            progress_cb=lambda d, t: self.progress.emit(d, t),
            done_cb=lambda ok, t: (self._mark_done(), self.finished.emit(ok, t)),
        )
        return True

    def cancel(self) -> None:
        if self._stop is not None:
            self._stop.set()
        self._stop = None

    def _mark_done(self) -> None:
        self._stop = None


class BuddyApp:
    def __init__(self, qt_app: QApplication) -> None:
        self.qt_app = qt_app
        self.store = Store()

        stored_style = self.store.get_meta("sprite_style", DEFAULT_SPRITE_STYLE)
        self.sprite_style = self._normalize_style(stored_style)
        if stored_style != self.sprite_style:
            self.store.set_meta("sprite_style", self.sprite_style)

        # Party: up to 3 active buddies. Each gets its own BuddyAgent
        # (PetWindow + animations + chatter + per-buddy state). The
        # singular `active_bag_id` still tracks the primary (slot 0) for
        # legacy code paths (wild catches, reminders, etc.).
        self.agents: list[BuddyAgent] = []
        self._build_agents_from_party()

        # Shared singletons — tray icon shows primary's sprite.
        # IMPORTANT: parent these to qt_app (application-scoped), NOT to
        # primary.window. Otherwise, when the primary buddy leaves the party
        # the rebuild cleanup deletes primary.window and Qt cascades-deletes
        # every child — tray icon disappears from the system tray, timers
        # stop, popups die, and the app effectively becomes unreachable.
        primary = self.primary
        self.tray = QSystemTrayIcon(
            _tray_icon(primary.buddy, self.sprite_style),
            parent=qt_app,
        )
        self.tray.setToolTip("Pokemon Buddy")
        self._build_tray_menu()
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

        self.bulk = _BulkDownloadAdapter(parent=qt_app)
        self.bulk.progress.connect(self._on_bulk_progress)
        self.bulk.finished.connect(self._on_bulk_finished)

        self._popup: Optional[BuddyMenuPopup] = None
        self._evolving_agent: Optional[BuddyAgent] = None
        # Strong refs to in-flight rare-catch star bursts so they survive
        # until the fade-out animation finishes.
        self._fanfare_bursts: list[StarBurst] = []

        qt_app.aboutToQuit.connect(self._save_positions)

        self.tick = QTimer(qt_app)
        self.tick.timeout.connect(self._on_tick)
        self.tick.start(TICK_MS)

        # Reminder + encounter + drop + schedule engines route through the
        # PRIMARY buddy only — keeps the soundscape from drowning the user
        # with three buddies saying the same lunch reminder.
        self.reminder_scheduler = ReminderScheduler(self.store,
                                                    parent=qt_app)
        self.reminder_scheduler.fired.connect(self.on_reminder_fired)
        self.reminder_scheduler.start()

        self.encounters = EncounterManager(self.store, primary.window,
                                           parent=qt_app)
        self.encounters.caught.connect(self.on_wild_caught)
        self.encounters.fled.connect(self.on_wild_fled)
        self.encounters.needs_pokeball.connect(self.on_needs_pokeball)
        self.encounters.start()

        self.item_drops = ItemDropManager(self.store, primary.window,
                                          parent=qt_app)
        self.item_drops.collected.connect(self.on_item_collected)
        self.item_drops.start()

        # Wall-clock scheduled greetings — 출근 / 점심 / 퇴근.
        self.schedule = DailyScheduleEngine(
            self.store, lambda: self.primary.buddy, parent=qt_app,
        )
        self.schedule.fired.connect(self._on_scheduled_event)
        self.schedule.start()

        primary.window.say("안녕! 같이 일하자 ✨", 3000)
        self._update_tray_status()

        # Diagnostic dump — helps when "pets don't show up" reports come in.
        for a in self.agents:
            log.info(
                "agent slot=%d bag_id=%d dex=%d visible=%s geom=%s "
                "sprite_geom=%s sprite_pixmap=%s",
                a.slot_index, a.buddy.bag_id, a.buddy.dex_id,
                a.window.isVisible(),
                (a.window.x(), a.window.y(),
                 a.window.width(), a.window.height()),
                (a.window.sprite.width(), a.window.sprite.height()),
                None if a.window.sprite._frame_pixmap is None
                else (a.window.sprite._frame_pixmap.width(),
                      a.window.sprite._frame_pixmap.height()),
            )

        prefetch_item_sprites([it.slug for it in ITEMS if it.slug])

    # ---- party helpers ----
    @property
    def primary(self) -> "BuddyAgent":
        """The slot-0 buddy. Always exists (Store guarantees ≥ 1)."""
        return self.agents[0]

    def _build_agents_from_party(self) -> None:
        """Load the party from the DB and instantiate a BuddyAgent for
        each slot. Used at startup and after big swaps (party changes
        invalidate which agents are live)."""
        party_ids = self.store.load_active_party()
        if not party_ids:
            # Defensive: Store guarantees at least one bag entry exists, so
            # bootstrap the party from whatever the active_bag_id pointer
            # was, or fall back to the first bag row.
            fallback = self.store.load_active_buddy()
            party_ids = [fallback.bag_id]
            self.store.save_active_party(party_ids)

        for slot, bag_id in enumerate(party_ids):
            buddy = self.store.get_bag_entry(bag_id)
            if buddy is None:
                continue
            if buddy.name.startswith("#"):
                resolved = get_name(buddy.dex_id)
                if resolved:
                    self.store.set_species_name(buddy.dex_id, resolved)
                    buddy = self.store.get_bag_entry(bag_id) or buddy
            agent = BuddyAgent(self.store, buddy, self.sprite_style,
                               slot_index=slot, parent=None)
            agent.popup_requested.connect(self.on_show_popup)
            agent.pet_requested.connect(self._on_agent_pet)
            agent.leveled_up.connect(self._on_agent_leveled_up)
            self.agents.append(agent)

    def _rebuild_agents(self) -> None:
        """Reconcile the on-screen agents with the current party. Buddies
        that stay in the party keep their PetWindow alive — only newcomers
        animate in and only dropped slots animate out. Eliminates the
        full-screen flicker the previous wholesale teardown caused."""
        # Defensive: close any open popup so its mouse grab doesn't outlive
        # the buddy it was anchored to.
        if self._popup is not None:
            try:
                self._popup.close()
            except RuntimeError:
                pass
            self._popup = None

        party_ids = self.store.load_active_party()
        if not party_ids:
            fallback = self.store.load_active_buddy()
            party_ids = [fallback.bag_id]
            self.store.save_active_party(party_ids)

        # Existing agents keyed by bag_id — survivors get re-used.
        by_id = {a.buddy.bag_id: a for a in self.agents}

        new_agents: list[BuddyAgent] = []
        for slot, bag_id in enumerate(party_ids):
            agent = by_id.pop(bag_id, None)
            if agent is not None:
                # Already on screen — keep window, just refresh metadata.
                agent.slot_index = slot
                agent.reload_buddy()
                new_agents.append(agent)
                continue
            buddy = self.store.get_bag_entry(bag_id)
            if buddy is None:
                continue
            if buddy.name.startswith("#"):
                resolved = get_name(buddy.dex_id)
                if resolved:
                    self.store.set_species_name(buddy.dex_id, resolved)
                    buddy = self.store.get_bag_entry(bag_id) or buddy
            new_agent = BuddyAgent(self.store, buddy, self.sprite_style,
                                   slot_index=slot, parent=None)
            new_agent.popup_requested.connect(self.on_show_popup)
            new_agent.pet_requested.connect(self._on_agent_pet)
            new_agent.leveled_up.connect(self._on_agent_leveled_up)
            new_agents.append(new_agent)

        # Anything still in by_id was dropped from the party — clean it up.
        for orphan in by_id.values():
            orphan.cleanup()

        self.agents = new_agents
        # Re-target shared engines at the (possibly new) primary's window.
        if self.agents:
            primary = self.primary
            self.encounters.buddy_widget = primary.window
            self.item_drops.buddy_widget = primary.window
        self._update_tray_status()

    def _save_positions(self) -> None:
        for agent in self.agents:
            try:
                agent.save_position()
            except Exception:  # noqa: BLE001
                pass
        # Close the SQLite handle so the next launch doesn't inherit a
        # lingering WAL / journal file from an unclean shutdown.
        try:
            self.store.close()
        except Exception:  # noqa: BLE001
            pass

    # ---- helpers ----
    @staticmethod
    def _normalize_style(stored: Optional[str]) -> str:
        """Old DBs may have 'bw_shiny' / 'showdown_shiny' stored — collapse
        those down to the two user-facing modes. Rare is now per-Pokemon."""
        if not stored:
            return DEFAULT_SPRITE_STYLE
        if stored.startswith("showdown"):
            return "showdown"
        if stored.startswith("bw"):
            return "bw"
        return DEFAULT_SPRITE_STYLE

    # ---- tray ----
    def _build_tray_menu(self) -> None:
        menu = QMenu()

        feed = QAction("밥 주기", menu)
        feed.triggered.connect(self.on_feed)
        menu.addAction(feed)

        play = QAction("놀아주기", menu)
        play.triggered.connect(self.on_play)
        menu.addAction(play)

        train = QAction("훈련", menu)
        train.triggered.connect(self.on_train)
        menu.addAction(train)

        menu.addSeparator()

        bag = QAction("내 포켓몬", menu)
        bag.triggered.connect(self.on_open_bag)
        menu.addAction(bag)

        inventory = QAction("내 가방", menu)
        inventory.triggered.connect(self.on_open_inventory)
        menu.addAction(inventory)

        dex = QAction("도감", menu)
        dex.triggered.connect(self.on_open_dex)
        menu.addAction(dex)

        status = QAction("스탯 보기", menu)
        status.triggered.connect(self.on_show_status)
        menu.addAction(status)

        menu.addSeparator()

        style_menu = menu.addMenu("스프라이트 스타일")
        self._style_group = QActionGroup(style_menu)
        self._style_group.setExclusive(True)
        for key, label in SPRITE_STYLES:
            act = QAction(label, style_menu)
            act.setCheckable(True)
            act.setChecked(key == self.sprite_style)
            act.triggered.connect(
                lambda _checked=False, k=key: self.on_change_style(k)
            )
            self._style_group.addAction(act)
            style_menu.addAction(act)

        bulk_act = QAction("에셋 일괄 다운로드 (Gen 1)", menu)
        bulk_act.triggered.connect(self.on_start_bulk)
        menu.addAction(bulk_act)

        menu.addSeparator()

        reminders_act = QAction("리마인더 설정…", menu)
        reminders_act.triggered.connect(self.on_open_reminder_dialog)
        menu.addAction(reminders_act)

        spawn_act = QAction("야생 포켓몬 소환 (테스트)", menu)
        spawn_act.triggered.connect(self.on_force_encounter)
        menu.addAction(spawn_act)

        custom_act = QAction("커스텀 포켓몬 추가…", menu)
        custom_act.triggered.connect(self.on_add_custom_pokemon)
        menu.addAction(custom_act)

        drop_act = QAction("아이템 떨어뜨리기 (테스트)", menu)
        drop_act.triggered.connect(self.on_force_item_drop)
        menu.addAction(drop_act)

        menu.addSeparator()

        reset_act = QAction("초기화…", menu)
        reset_act.triggered.connect(self.on_reset_data)
        menu.addAction(reset_act)

        quit_act = QAction("종료", menu)
        quit_act.triggered.connect(self.on_quit)
        menu.addAction(quit_act)

        self.tray.setContextMenu(menu)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            # Toggle ALL party members' visibility together (based on the
            # primary's current state) so the user gets a single switch.
            target_visible = not self.primary.window.isVisible()
            for agent in self.agents:
                agent.window.setVisible(target_visible)

    # ---- actions ----
    # Action handlers now operate on the agent the user actually clicked
    # (popup is per-buddy). The tray menu uses the primary by default.
    def on_feed(self, agent: Optional[BuddyAgent] = None) -> None:
        (agent or self.primary).on_feed()

    def on_play(self, agent: Optional[BuddyAgent] = None) -> None:
        (agent or self.primary).on_play()

    def on_train(self, agent: Optional[BuddyAgent] = None) -> None:
        (agent or self.primary).on_train()

    def _on_agent_pet(self, agent: BuddyAgent) -> None:
        """Left-click on a buddy. Routed via agent's `pet_requested` so the
        right buddy gets the friendship bump."""
        agent.on_pet()

    def on_show_status(self) -> None:
        b = self.primary.buddy
        text = (
            f"{b.display_name}  ·  Lv.{b.level}\n"
            f"종족 : {b.species_label}\n"
            f"EXP : {b.exp} / {b.exp_to_next}\n"
            f"친밀도 : {b.friendship} / 100\n"
            f"기분 : {b.mood}"
        )
        QMessageBox.information(self.primary.window, "Pokemon Buddy", text)
        self._update_tray_status()

    def on_quit(self) -> None:
        self._save_positions()
        self.qt_app.quit()

    # ---- reminders ----
    def on_reminder_fired(self, reminder: Reminder) -> None:
        # Reminders speak through the primary buddy only, otherwise three
        # voices would shout the same "물 마시자" at the user.
        self.primary.window.say(reminder.message, 4000)
        self.tray.showMessage(
            f"💡 {reminder.name}",
            reminder.message,
            QSystemTrayIcon.Information,
            5000,
        )

    # ---- main panel (single dialog hosting all four tabs) ----
    def on_open_main(self, initial_tab: str = NAV_POKEMON) -> None:
        """Open the single MainPanel window on the requested tab. If it's
        already open, just switch tabs in the existing window."""
        existing = getattr(self, "_main_panel", None)
        if existing is not None:
            # The previous panel may already be a stale C++ pointer (its Qt
            # parent was deleted when a party member left). Probe defensively.
            try:
                visible = existing.isVisible()
            except RuntimeError:
                self._main_panel = None
                existing = None
                visible = False
            if existing is not None and visible:
                existing._switch_tab(initial_tab)
                existing.raise_()
                existing.activateWindow()
                return

        # Parent=None: keep the panel application-scoped so a party rebuild
        # can't cascade-delete it via the primary PetWindow.
        dlg = MainPanel(self.store, self.sprite_style,
                        self.primary.buddy.bag_id, initial_tab=initial_tab,
                        parent=None)
        dlg.set_as_buddy.connect(self.on_swap_buddy)
        dlg.reminders_saved.connect(self.reminder_scheduler.check_now)
        dlg.schedule_saved.connect(self.schedule.check_now)
        dlg.use_item_requested.connect(self.on_use_item)
        dlg.show_detail.connect(self.on_show_pokemon_detail)
        dlg.bag_changed.connect(self._on_bag_changed)
        self._main_panel = dlg
        dlg.finished.connect(lambda _r: self._on_main_panel_closed())
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _on_bag_changed(self) -> None:
        """BagPanel emits this after rename / release / party toggle. If
        the active party set actually changed, rebuild all agents;
        otherwise just refresh each agent's loaded state."""
        current_ids = [a.buddy.bag_id for a in self.agents]
        party_now = self.store.load_active_party()
        if party_now != current_ids:
            log.info("party changed: %s -> %s", current_ids, party_now)
            self._rebuild_agents()
        else:
            log.info("bag changed (rename/release) — refreshing agents")
            for a in self.agents:
                a.reload_buddy()
            self._update_tray_status()

    def _on_main_panel_closed(self) -> None:
        self._main_panel = None

    # Backwards-compatible shortcuts used by tray menu + popup actions.
    def on_open_bag(self) -> None:
        self.on_open_main(NAV_POKEMON)

    def on_open_inventory(self) -> None:
        self.on_open_main(NAV_INVENTORY)

    def on_open_dex(self) -> None:
        self.on_open_main(NAV_DEX)

    def on_open_reminder_dialog(self) -> None:
        self.on_open_main(NAV_REMINDERS)

    # ---- buddy popup (replaces right-click menu) ----
    def on_show_popup(self, agent: BuddyAgent, anchor_rect) -> None:
        """Right-click on a specific buddy. The popup remembers which
        agent it's for so the action handler targets the same one."""
        # Tear down any prior popup before opening a new one. With 2+ buddies
        # out a stale Qt.Popup widget would keep the mouse grab and the next
        # popup's buttons felt dead. Popups are WA_DeleteOnClose, so close()
        # also schedules destruction.
        prev = self._popup
        self._popup = None
        if prev is not None:
            try:
                prev.close()
            except RuntimeError:
                pass
        popup = BuddyMenuPopup(agent.buddy, parent=None)
        popup.action.connect(
            lambda key, a=agent: self._on_popup_action(key, a)
        )
        popup.destroyed.connect(self._on_popup_destroyed)
        self._popup = popup
        popup.show_animated(anchor_rect)

    def _on_popup_destroyed(self, obj) -> None:
        if self._popup is obj:
            self._popup = None

    def _on_popup_action(self, key: str, agent: BuddyAgent) -> None:
        if key == ACTION_FEED:
            self.on_feed(agent)
        elif key == ACTION_PLAY:
            self.on_play(agent)
        elif key == ACTION_TRAIN:
            self.on_train(agent)
        elif key == ACTION_BAG:
            self.on_open_bag()
        elif key == ACTION_INVENTORY:
            self.on_open_inventory()
        elif key == ACTION_DEX:
            self.on_open_dex()
        elif key == ACTION_RENAME:
            self.on_rename_buddy(agent)
        elif key == ACTION_DETAIL:
            self.on_show_pokemon_detail(agent.buddy.bag_id)

    def on_rename_buddy(self, agent: Optional[BuddyAgent] = None) -> None:
        target_agent = agent or self.primary
        self._rename_bag_entry(target_agent.buddy.bag_id, agent=target_agent)

    def _rename_bag_entry(self, bag_id: int, *,
                          agent: Optional[BuddyAgent] = None) -> None:
        target = self.store.get_bag_entry(bag_id)
        if target is None:
            return
        current = target.nickname or ""
        parent_window = (agent.window if agent else self.primary.window)
        name, ok = QInputDialog.getText(
            parent_window, "이름 변경",
            f"{target.species_label}의 새 이름:",
            text=current,
        )
        if not ok:
            return
        name = name.strip()
        new_nick = name or None
        self.store.rename_bag_entry(bag_id, new_nick)
        # Refresh the agent (if this buddy is in the party).
        for a in self.agents:
            if a.buddy.bag_id == bag_id:
                a.reload_buddy()
                a.window.say(f"이제 내 이름은 {a.buddy.display_name}!", 2200)
                break

    # ---- item drops ----
    def on_item_collected(self, item_key: str) -> None:
        item = find_item(item_key)
        if item is None:
            return
        self.store.add_item(item_key, 1)
        self.primary.window.say(f"{item.emoji} {item.label} 획득!", 2000)
        self.primary.anim.play("happy")

    def on_needs_pokeball(self) -> None:
        self.primary.window.say("몬스터볼이 없어! 🔴 모아야 해…", 2400)

    def on_show_pokemon_detail(self, bag_id: int) -> None:
        """Open the read-only detail dialog for a specific bag entry. Parent
        is the MainPanel so the detail dialog stays on top of it."""
        target = self.store.get_bag_entry(bag_id)
        if target is None:
            return
        parent = getattr(self, "_main_panel", None) or self.primary.window
        dlg = PokemonDetailDialog(target, self.sprite_style, parent=parent)
        dlg.display_scale_changed.connect(self._on_display_scale_changed)
        dlg.exec()

    def _on_display_scale_changed(self, dex_id: int, scale: float) -> None:
        """Live-refresh every party member currently rendering `dex_id` so
        the user sees the size change without restarting."""
        for agent in self.agents:
            if agent.buddy.dex_id == dex_id:
                agent.window.sprite.set_scale_override(scale)

    # ---- using special items ----
    def on_use_item(self, item_key: str) -> None:
        log.info("on_use_item key=%s agents=%d", item_key, len(self.agents))
        item = find_item(item_key)
        if item is None:
            log.debug("item not found for key=%s", item_key)
            return

        # Master ball arms the NEXT wild catch — it isn't owned by any
        # individual buddy, so it skips the picker and routes through
        # primary as the narrator.
        if item_key == "special.master-ball":
            if not self.store.consume_item(item_key, 1):
                self.primary.window.say("아이템이 없어!", 1800)
                return
            self.store.set_meta("master_ball_pending", "1")
            self.primary.window.say(
                "💎 마스터볼 장착! 다음 야생은 무조건 잡혀 ✨", 2800,
            )
            self.primary.anim.play("happy")
            self._refresh_main_inventory()
            self._update_tray_status()
            return

        # Everything else applies to a specific party member — ask which.
        # Hide every other Qt.WindowStaysOnTopHint surface (buddies AND the
        # main panel) so the picker isn't competing for foreground. With
        # both staysOnTop the picker can render behind main_panel and feel
        # frozen — that's what was making "Use" silently fail.
        from .buddy_picker import pick_buddy
        was_visible = [(a, a.window.isVisible()) for a in self.agents]
        log.debug("hiding %d buddies for picker", len(was_visible))
        for agent in self.agents:
            agent.window.hide()
        mp = getattr(self, "_main_panel", None)
        mp_was_visible = bool(mp is not None and mp.isVisible())
        if mp_was_visible:
            log.debug("hiding main panel for picker")
            mp.hide()
        target = None
        try:
            target = pick_buddy(self.agents, item.label, parent=None)
        except Exception:  # noqa: BLE001
            log.exception("  pick_buddy raised")
            target = None
        finally:
            log.debug("picker done, restoring windows")
            for agent, was_vis in was_visible:
                if was_vis:
                    try:
                        agent.window.show()
                    except RuntimeError:
                        log.exception("  agent.window.show() failed")
            if mp_was_visible and mp is not None:
                try:
                    mp.show()
                    mp.raise_()
                except RuntimeError:
                    log.exception("  main panel show() failed")
        log.debug("picker returned target=%s",
                 target.buddy.display_name if target else None)
        if target is None:
            return

        if (item.kind == ItemKind.SPECIAL and item.slug
                and item.slug.endswith("-stone")):
            target_dex = get_stone_evolution_target(
                target.buddy.dex_id, item.slug,
            )
            log.debug("stone %s on %s -> evo target=%s",
                     item.slug, target.buddy.display_name, target_dex)
            if target_dex is None:
                target.window.say(
                    f"{target.buddy.display_name}에겐 효과가 없어…", 2400,
                )
                return
            if not self.store.consume_item(item_key, 1):
                target.window.say("아이템이 없어!", 1800)
                return
            new_species = get_name(target_dex)
            self._do_evolve_agent(target, target_dex, new_species)
            self._refresh_main_inventory()
            return

        if not self.store.consume_item(item_key, 1):
            log.debug("consume_item failed for key=%s", item_key)
            target.window.say("아이템이 없어!", 1800)
            return
        log.debug("applying %s to %s", item_key, target.buddy.display_name)

        if item_key == "special.potion":
            self.store.bump_friendship_points(target.buddy, 10)
            target.reload_buddy()
            target.window.say("💊 친밀도 +10 ❤️", 2200)
            target.anim.play("happy")
        elif item_key == "special.super-potion":
            self.store.bump_friendship_points(target.buddy, 25)
            target.reload_buddy()
            target.window.say("💊 친밀도 +25 ❤️", 2200)
            target.anim.play("happy")
        elif item_key == "special.hyper-potion":
            self.store.bump_friendship_points(target.buddy, 50)
            target.reload_buddy()
            target.window.say("💊 친밀도 +50 ❤️❤️", 2400)
            target.anim.play("happy")
        elif item_key == "special.rare-candy":
            leveled = self.store.gain_exp(target.buddy, 100)
            target.reload_buddy()
            if leveled:
                target._after_level_up()
            else:
                target.window.say("🍬 EXP +100!", 2400)
                target.anim.play("surprised")
        else:
            log.info("unhandled special item %s", item_key)
            self.store.add_item(item_key, 1)
            return

        self._refresh_main_inventory()
        self._update_tray_status()

    def _refresh_main_inventory(self) -> None:
        mp = getattr(self, "_main_panel", None)
        if mp is not None:
            mp.refresh_inventory()

    def on_swap_buddy(self, bag_id: int) -> None:
        """User clicked 'set as primary' on a bag card. Move the buddy into
        slot 0 and rebuild the on-screen agents to match."""
        if bag_id == self.primary.buddy.bag_id:
            return
        log.info("swap primary -> bag_id=%d", bag_id)
        target = self.store.get_bag_entry(bag_id)
        if target is None:
            log.debug("on_swap_buddy ignored — bag id=%d not found", bag_id)
            return
        self.store.swap_active_buddy(bag_id)
        self._rebuild_agents()
        # Bag panel's "대표/파티" badges + card borders are stale after the
        # swap — refresh so the user sees the new primary highlighted right
        # away. update_active_bag_id keeps any open MainPanel pointer aligned.
        mp = getattr(self, "_main_panel", None)
        if mp is not None:
            mp.update_active_bag_id(bag_id)
            mp.refresh_bag()
        new_primary = self.primary
        new_primary.window.say(
            f"이제부터 {new_primary.buddy.display_name}랑 함께! "
            f"Lv.{new_primary.buddy.level} 🎉",
            2800,
        )
        new_primary.anim.play("surprised")

    # ---- sprite style ----
    def on_change_style(self, key: str) -> None:
        key = self._normalize_style(key)
        if key == self.sprite_style:
            return
        self.sprite_style = key
        self.store.set_meta("sprite_style", key)
        for agent in self.agents:
            agent.set_sprite_style(key)
        self._update_tray_icon()
        label = next((lbl for k, lbl in SPRITE_STYLES if k == key), key)
        self.primary.window.say(f"스타일: {label}", 1800)

    def on_start_bulk(self) -> None:
        if self.bulk.is_running():
            self.primary.window.say("이미 다운로드 중이야", 1800)
            return
        lo, hi = BULK_DEX_RANGE
        ok = self.bulk.start(self.sprite_style, range(lo, hi + 1))
        if ok:
            self.primary.window.say(f"에셋 다운로드 시작 ({hi - lo + 1}마리)", 2200)

    def _on_bulk_progress(self, done: int, total: int) -> None:
        if done == total or done % 10 == 0:
            self.tray.setToolTip(f"Pokemon Buddy — 다운로드 {done}/{total}")

    def _on_bulk_finished(self, ok: int, total: int) -> None:
        # No Windows toast — only reminders push system notifications.
        self.primary.window.say(f"에셋 다운로드 완료! ({ok}/{total})", 2400)
        self._update_tray_status()

    # ---- wild encounters ----
    def on_force_encounter(self) -> None:
        self.encounters.force_spawn()

    def on_add_custom_pokemon(self) -> None:
        """Open the custom-pokemon registration dialog. On accept, copies
        the chosen GIF(s) into the assets dir under a freshly minted dex_id,
        drops a fresh individual into the bag, and refreshes any open bag
        panel. The new dex_id also joins the wild encounter pool."""
        log.debug("on_add_custom_pokemon: opening dialog")
        was_visible = [(a, a.window.isVisible()) for a in self.agents]
        for agent in self.agents:
            agent.window.hide()
        try:
            dlg = CustomPokemonDialog(parent=None)
            log.debug("about to call dlg.exec()")
            result = dlg.exec()
            log.debug("dlg.exec() returned %r (Accepted=%r)",
                     int(result), int(dlg.Accepted))
            accepted = result == dlg.Accepted
        finally:
            log.debug("entering finally — restoring buddies")
            for agent, was_vis in was_visible:
                if was_vis:
                    agent.window.show()
            log.debug("buddies restored")
        if not accepted:
            log.debug("dialog rejected/cancelled — no add")
            return
        log.debug("dialog accepted, name=%r base=%s extra=%s",
                 dlg.name_ko, dlg.base_path, dlg.extra_path)
        try:
            dex_id = custom_pokemon.add(
                name_ko=dlg.name_ko,
                gif_base_path=dlg.base_path,
                gif_extra_path=dlg.extra_path,
                name_eng=dlg.name_eng,
                display_scale=dlg.display_scale,
            )
        except (ValueError, OSError) as exc:
            log.error("custom pokemon add failed: %s", exc)
            self.primary.window.say(f"등록 실패: {exc}", 3000)
            return
        log.info("registered as dex_id=%d, adding to bag", dex_id)
        self.store.add_to_bag(dex_id)
        # Also stamp the dex so the encyclopedia shows the new species as
        # caught (count 1) instead of an unseen silhouette.
        self.store.record_catch(dex_id, dlg.name_ko, is_rare=False)
        mp = getattr(self, "_main_panel", None)
        if mp is not None:
            mp.refresh_bag()
            mp.refresh_dex()
        self.primary.window.say(
            f"{dlg.name_ko} (#{dex_id})을(를) 가방+도감에 추가했어!", 3500
        )

    def on_force_item_drop(self) -> None:
        self.item_drops.force_spawn()

    # ---- reset ----
    def on_reset_data(self) -> None:
        confirm = QMessageBox.question(
            self.primary.window, "초기화",
            "모든 포켓몬·도감·가방 데이터를 지우고 새로 시작할까?\n"
            "(리마인더와 창 위치는 유지)",
        )
        if confirm != QMessageBox.Yes:
            return
        mp = getattr(self, "_main_panel", None)
        if mp is not None:
            mp.close()
        self.store.reset_all_data()
        # Tear down all party windows and rebuild from the freshly-seeded
        # starter party.
        self._rebuild_agents()
        self.primary.window.say("처음부터 다시 시작! ✨", 3000)
        self.primary.anim.play("surprised")

    # ---- wild caught (rewards go to primary buddy) ----
    def on_wild_caught(self, dex_id: int, name: str, is_rare: bool,
                       ball_key: str = "pokeball.basic") -> None:
        log.info("caught wild: dex=%d name=%s rare=%s ball=%s",
                 dex_id, name, is_rare, ball_key)
        display_species = f"레어 {name}" if is_rare else name
        entry = self.store.record_catch(dex_id, name, is_rare=is_rare)
        self.store.add_to_bag(dex_id, is_rare=is_rare, caught_with=ball_key)
        mp = getattr(self, "_main_panel", None)
        if mp is not None:
            mp.refresh_bag()
        primary = self.primary
        leveled = self.store.gain_exp(primary.buddy, CATCH_EXP_REWARD)
        self.store.bump_friendship(
            primary.buddy,
            FRIENDSHIP_CATCH_WILD + (FRIENDSHIP_LEVEL_UP if leveled else 0),
        )
        primary.reload_buddy()

        first_time = entry.count == 1
        if is_rare and first_time:
            primary.window.say(
                f"✨ 레어한 새 포켓몬 {name}!!! 도감에 추가됐어!", 4000,
            )
        elif is_rare:
            primary.window.say(f"✨ 레어한 {name}을(를) 잡았다!!!", 3500)
        elif first_time:
            primary.window.say(
                f"🎉 새로운 포켓몬 {name}! 도감에 추가됐어!", 3500,
            )
        else:
            primary.window.say(
                f"{display_species} 또 잡았다! 가방에 추가됨", 2800,
            )
        primary.anim.play("surprised")
        # Rare catches get a fanfare: a star burst over every party member.
        if is_rare:
            self._play_party_fanfare()
        if leveled:
            QTimer.singleShot(1200, primary._after_level_up)
        self._update_tray_status()

    def _play_party_fanfare(self) -> None:
        """Star burst over every party member's head. Used to mark a rare
        catch so all on-screen buddies share in the moment."""
        for agent in self.agents:
            burst = StarBurst()
            geo = agent.window.frameGeometry()
            # Land the burst above the buddy's head, not on it — feels more
            # like a celebration popping up rather than an effect hugging
            # the sprite.
            center = geo.center()
            center.setY(geo.top() - 4)
            burst.play_at(
                center,
                on_done=lambda b=burst: self._cleanup_fanfare_burst(b),
            )
            self._fanfare_bursts.append(burst)

    def _cleanup_fanfare_burst(self, burst: StarBurst) -> None:
        try:
            burst.hide()
            burst.deleteLater()
        except RuntimeError:
            pass
        try:
            self._fanfare_bursts.remove(burst)
        except ValueError:
            pass

    # ---- per-agent level-up routing ----
    def _on_agent_leveled_up(self, agent: BuddyAgent) -> None:
        """Each agent emits this when its buddy levels up. We defer the
        evolution dialog by 1.5s so the surprise pop + halo can land first."""
        QTimer.singleShot(1500, lambda: self._maybe_offer_evolution(agent))

    def _maybe_offer_evolution(self, agent: BuddyAgent) -> None:
        target = can_evolve(agent.buddy.dex_id, agent.buddy.level)
        if target is None:
            return
        before_name = agent.buddy.display_name
        after_species = get_name(target)
        before_path = get_buddy_sprite_with_fallback(
            self.sprite_style, agent.buddy.dex_id, agent.buddy.is_rare,
        )
        after_path = get_buddy_sprite_with_fallback(
            self.sprite_style, target, agent.buddy.is_rare,
        )
        dlg = EvolutionDialog(
            before_name, after_species, before_path, after_path,
            parent=agent.window,
        )
        if dlg.exec() == EvolutionDialog.Accepted:
            self._do_evolve_agent(agent, target, after_species)
        else:
            agent.window.say("아직은 이대로 좋아!", 2000)

    def _do_evolve_agent(self, agent: BuddyAgent, new_dex_id: int,
                         new_species_name: str) -> None:
        log.info("evolve bag_id=%d: %d -> %d (%s)",
                 agent.buddy.bag_id, agent.buddy.dex_id,
                 new_dex_id, new_species_name)
        old_display = agent.buddy.display_name
        self.store.record_catch(new_dex_id, new_species_name,
                                is_rare=agent.buddy.is_rare)
        # Mutate this agent's bag row directly (not necessarily the active
        # pointer) so non-primary agents can evolve too.
        self.store.evolve_bag_entry(agent.buddy.bag_id, new_dex_id)
        agent.reload_buddy()
        if agent.buddy.name.startswith("#"):
            self.store.set_species_name(new_dex_id, new_species_name)
            agent.reload_buddy()
        agent.window.say(
            f"진화! {old_display} → {agent.buddy.display_name} ✨", 3500,
        )
        agent.anim.play("surprised")
        if agent is self.primary:
            self._update_tray_icon()
        self._update_tray_status()

    def on_wild_fled(self, dex_id: int, name: str, is_rare: bool) -> None:
        if not name or not name.strip():
            name = f"#{dex_id:04d}"
        display = f"레어 {name}" if is_rare else name
        self.primary.window.say(f"{display}이(가) 도망갔네…", 2200)

    def _on_scheduled_event(self, text: str) -> None:
        """Wall-clock greeting (출근 / 점심 / 퇴근) from the primary buddy."""
        self.primary.window.say(text, 4500)
        self.primary.anim.play("happy")

    # ---- background tick ----
    def _on_tick(self) -> None:
        if is_screen_locked():
            return
        for agent in self.agents:
            agent.apply_passive_gain()
        self._update_tray_status()

    # ---- tray helpers ----
    def _update_tray_status(self) -> None:
        b = self.primary.buddy
        hearts = "❤️" * b.hearts + "♡" * (5 - b.hearts)
        text = (
            f"{b.display_name}  Lv.{b.level}  {hearts}\n"
            f"EXP {b.exp}/{b.exp_to_next}  ·  친밀도 {b.friendship}/100"
        )
        self.tray.setToolTip(text)

    def _update_tray_icon(self) -> None:
        self.tray.setIcon(_tray_icon(self.primary.buddy, self.sprite_style))


def _set_windows_app_id(app_id: str) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception as exc:  # noqa: BLE001
        log.debug("AppUserModelID set failed: %s", exc)


def main() -> int:
    # Two-tier logging:
    #   debug.log (file) ← DEBUG and up — full system trace, useful when
    #     hunting bugs without restarting the user.
    #   stderr (console) ← INFO and up — only user-facing actions show up
    #     in the terminal so it stays readable.
    # pythonw.exe drops stderr but writes the file regardless.
    from .config import ROOT
    log_path = ROOT / "debug.log"
    file_h = logging.FileHandler(str(log_path), encoding="utf-8")
    file_h.setLevel(logging.DEBUG)
    file_h.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    ))
    stream_h = logging.StreamHandler()
    stream_h.setLevel(logging.INFO)
    stream_h.setFormatter(logging.Formatter(
        "%(levelname)s %(name)s: %(message)s"
    ))
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[file_h, stream_h],
        force=True,  # nuke any handlers other imports may have installed
    )

    _set_windows_app_id(APP_ID)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("So-On-Park")
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, APP_NAME,
                             "시스템 트레이를 사용할 수 없는 환경입니다.")
        return 1

    buddy_app = BuddyApp(app)
    app.setWindowIcon(_tray_icon(buddy_app.primary.buddy, buddy_app.sprite_style))
    _ = buddy_app
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
