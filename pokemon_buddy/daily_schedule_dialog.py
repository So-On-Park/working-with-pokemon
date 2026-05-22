"""Schedule editor panel — 출근 / 점심 / 퇴근 + 사용자 정의 알람.

Three built-in alarms (출근/점심/퇴근) have fixed labels and pull their
text from personality-flavored banks in `messages.py`. They're not
deletable — the user disables them by unchecking instead.

Custom alarms are user-created rows with editable label, editable
message text (used verbatim when the alarm fires), and a delete button.
'＋ 새 알람 추가' appends a fresh row; '저장' commits both edits and
deletions to the DB and prompts `DailyScheduleEngine.check_now()` so a
freshly-due alarm fires immediately."""

from __future__ import annotations

import time as _time
from typing import List, Optional, Set

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .state import DailyEvent, Store


class _AlarmRow(QFrame):
    """One editable alarm. Built-in rows have a fixed label + 'personality
    bank' hint instead of a free-text message + delete button."""

    delete_clicked = Signal(object)  # self

    def __init__(self, event: Optional[DailyEvent],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # event=None marks a freshly-added row that hasn't been persisted
        # yet — on save it'll become a brand-new custom alarm.
        self.is_new = event is None
        self.event_key = None if event is None else event.key
        self.is_builtin = bool(event and event.is_builtin)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "_AlarmRow { border: 1px solid #d8d8d8; border-radius: 6px; "
            "background: #fbfbfb; }"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(4)

        # ---- top row: enabled + label + delete ----
        top = QHBoxLayout()
        top.setSpacing(6)

        self.cb = QCheckBox()
        self.cb.setChecked(True if event is None else event.enabled)
        top.addWidget(self.cb)

        if self.is_builtin:
            lab = QLabel(event.label)
            lf = QFont(); lf.setBold(True); lf.setPointSize(10)
            lab.setFont(lf)
            top.addWidget(lab)
            top.addStretch(1)
            badge = QLabel("기본")
            badge.setStyleSheet(
                "color: #666; background: #ececec;"
                "border-radius: 4px; padding: 1px 6px; font-size: 8pt;"
            )
            top.addWidget(badge)
            self.label_edit = None
        else:
            self.label_edit = QLineEdit(event.label if event else "")
            self.label_edit.setPlaceholderText("이름 (예: 회의)")
            self.label_edit.setMinimumWidth(120)
            top.addWidget(self.label_edit, stretch=1)
            del_btn = QPushButton("✕")
            del_btn.setToolTip("이 알람 삭제")
            del_btn.setFixedSize(24, 24)
            del_btn.setStyleSheet(
                "QPushButton { color: #b04040; font-weight: bold;"
                "  border: 1px solid #d8b0b0; border-radius: 4px;"
                "  background: #fff5f5; }"
                "QPushButton:hover { background: #ffe5e5; }"
            )
            del_btn.clicked.connect(lambda: self.delete_clicked.emit(self))
            top.addWidget(del_btn)

        outer.addLayout(top)

        # ---- bottom row: message + time spinboxes ----
        bottom = QHBoxLayout()
        bottom.setSpacing(6)

        if self.is_builtin:
            hint = QLabel("(성격에 맞는 멘트를 자동으로 골라줘)")
            hint.setStyleSheet("color: #888; font-size: 8pt;")
            bottom.addWidget(hint, stretch=1)
            self.message_edit = None
        else:
            self.message_edit = QLineEdit(event.message if event else "")
            self.message_edit.setPlaceholderText("이때 할 말 (예: 회의 시작!)")
            bottom.addWidget(self.message_edit, stretch=1)

        self.hour = QSpinBox()
        self.hour.setRange(0, 23)
        self.hour.setSuffix(" 시")
        self.hour.setValue(event.hour if event else 12)
        self.hour.setFixedWidth(80)
        self.hour.setMinimumHeight(28)
        self.hour.setStyleSheet("QSpinBox { padding: 2px 6px; font-size: 10pt; }")
        bottom.addWidget(self.hour)

        self.minute = QSpinBox()
        self.minute.setRange(0, 59)
        self.minute.setSuffix(" 분")
        self.minute.setValue(event.minute if event else 0)
        self.minute.setFixedWidth(80)
        self.minute.setMinimumHeight(28)
        self.minute.setStyleSheet("QSpinBox { padding: 2px 6px; font-size: 10pt; }")
        bottom.addWidget(self.minute)

        outer.addLayout(bottom)

    # ---- accessors ----
    def is_blank_custom(self) -> bool:
        """A freshly-added custom row that the user never filled in. We
        skip persisting these silently on save."""
        if self.is_builtin:
            return False
        label = (self.label_edit.text().strip() if self.label_edit else "")
        message = (self.message_edit.text().strip()
                   if self.message_edit else "")
        return not label and not message

    def collect(self) -> dict:
        """Build a kwargs dict for Store.add_custom_alarm /
        update_schedule_event."""
        return {
            "key": self.event_key,
            "label": (self.label_edit.text().strip()
                      if self.label_edit else None),
            "message": (self.message_edit.text().strip()
                        if self.message_edit else None),
            "hour": int(self.hour.value()),
            "minute": int(self.minute.value()),
            "enabled": bool(self.cb.isChecked()),
            "is_builtin": self.is_builtin,
            "is_new": self.is_new,
        }


class DailySchedulePanel(QWidget):
    """일정 tab inside MainPanel."""

    saved = Signal()

    def __init__(self, store: Store, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self._rows: List[_AlarmRow] = []
        self._deleted_keys: Set[str] = set()

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(6)

        hint = QLabel(
            "평일 시계 시간 기준 알람이야. PC가 꺼져있거나 잠금 상태일 땐 안 떠. "
            "기본 알람은 성격별로 자동 멘트, 사용자 알람은 메시지를 직접 정해."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #555; font-size: 8pt;")
        root.addWidget(hint)

        # Scrollable list of alarm rows.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        self._inner = QWidget()
        self._inner_layout = QVBoxLayout(self._inner)
        self._inner_layout.setSpacing(4)
        self._inner_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self._inner)
        root.addWidget(scroll, stretch=1)

        # Populate rows from the DB.
        for event in self.store.list_schedule_events():
            self._append_row(event)
        self._inner_layout.addStretch(1)

        # Footer: add + save.
        btn_row = QHBoxLayout()
        add_btn = QPushButton("＋ 새 알람 추가")
        add_btn.setFixedHeight(28)
        add_btn.clicked.connect(self._on_add_clicked)
        btn_row.addWidget(add_btn)
        btn_row.addStretch(1)
        save_btn = QPushButton("저장")
        save_btn.setDefault(True)
        save_btn.setFixedHeight(28)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)

    def cleanup(self) -> None:
        pass

    # ---- row management ----
    def _append_row(self, event: Optional[DailyEvent]) -> _AlarmRow:
        row = _AlarmRow(event, parent=self._inner)
        row.delete_clicked.connect(self._on_delete_row)
        # Insert before the trailing stretch (if it exists) so new rows
        # don't end up below the spacer.
        count = self._inner_layout.count()
        insert_at = count
        if count > 0:
            last = self._inner_layout.itemAt(count - 1)
            if last is not None and last.spacerItem() is not None:
                insert_at = count - 1
        self._inner_layout.insertWidget(insert_at, row)
        self._rows.append(row)
        return row

    def _on_add_clicked(self) -> None:
        self._append_row(None)

    def _on_delete_row(self, row: _AlarmRow) -> None:
        if row.event_key is not None:
            self._deleted_keys.add(row.event_key)
        try:
            self._rows.remove(row)
        except ValueError:
            pass
        row.setParent(None)
        row.deleteLater()

    # ---- save ----
    def _on_save(self) -> None:
        # Apply deletions first so a delete-then-recreate at the same key
        # (very rare, but possible if user keeps clicking) ends up with
        # the recreated version, not the deleted one.
        for key in self._deleted_keys:
            self.store.delete_schedule_event(key)
        self._deleted_keys.clear()

        for row in list(self._rows):
            data = row.collect()
            if data["is_builtin"]:
                # Only time + enable are editable for built-ins. Label /
                # message are derived in code, so pass None to leave the
                # DB columns alone.
                self.store.update_schedule_event(
                    data["key"], data["hour"], data["minute"],
                    data["enabled"],
                )
                continue
            # Custom row — skip if it's blank (user added then changed mind).
            if row.is_blank_custom():
                continue
            label = data["label"] or "알람"
            message = data["message"] or label  # fall back to label as text
            if data["is_new"] or not data["key"]:
                new_key = self.store.add_custom_alarm(
                    label=label, message=message,
                    hour=data["hour"], minute=data["minute"],
                    enabled=data["enabled"],
                )
                row.event_key = new_key
                row.is_new = False
            else:
                self.store.update_schedule_event(
                    data["key"], data["hour"], data["minute"],
                    data["enabled"],
                    label=label, message=message,
                )

        self.saved.emit()
