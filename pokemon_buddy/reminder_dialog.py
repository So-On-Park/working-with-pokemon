"""Reminder editor panel. Edits are committed on Save; closing MainPanel
without saving discards them (same as the old Cancel behavior)."""

from __future__ import annotations

import time
from typing import Set

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .state import Reminder, Store


COL_ENABLED = 0
COL_NAME = 1
COL_MESSAGE = 2
COL_INTERVAL = 3
COL_DELETE = 4


class ReminderPanel(QWidget):
    """Edit reminders. Hosted inside MainPanel as one tab."""

    saved = Signal()

    def __init__(self, store: Store, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self._deleted_ids: Set[int] = set()

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 2, 4, 2)
        root.setSpacing(4)

        hint = QLabel(
            "체크하면 활성화. 메시지·간격을 자유롭게 바꿀 수 있고, "
            "＋ 버튼으로 새 리마인더도 추가돼."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #555; font-size: 8pt;")
        root.addWidget(hint)

        self.table = QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels(["✓", "이름", "메시지", "분", ""])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_ENABLED, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(COL_NAME, QHeaderView.Interactive)
        header.setSectionResizeMode(COL_MESSAGE, QHeaderView.Stretch)
        header.setSectionResizeMode(COL_INTERVAL, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(COL_DELETE, QHeaderView.ResizeToContents)
        self.table.setColumnWidth(COL_NAME, 80)
        root.addWidget(self.table, stretch=1)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("＋")
        add_btn.setToolTip("새 리마인더 추가")
        add_btn.setFixedSize(32, 26)
        add_btn.clicked.connect(self._on_add_row)
        btn_row.addWidget(add_btn)
        btn_row.addStretch(1)

        save_btn = QPushButton("저장")
        save_btn.setDefault(True)
        save_btn.setFixedHeight(26)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        root.addLayout(btn_row)

        self._populate()

    def cleanup(self) -> None:
        pass

    # ---- table population ----
    def _populate(self) -> None:
        for r in self.store.list_reminders():
            self._append_row(r)

    def _append_row(self, r: Reminder | None) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        enabled_widget = QWidget()
        enabled_layout = QHBoxLayout(enabled_widget)
        enabled_layout.setContentsMargins(0, 0, 0, 0)
        enabled_layout.setAlignment(Qt.AlignCenter)
        cb = QCheckBox()
        cb.setChecked(r.enabled if r else True)
        enabled_layout.addWidget(cb)
        self.table.setCellWidget(row, COL_ENABLED, enabled_widget)

        name_item = QTableWidgetItem(r.name if r else "새 알림")
        self.table.setItem(row, COL_NAME, name_item)

        msg_item = QTableWidgetItem(r.message if r else "메시지를 입력하세요")
        self.table.setItem(row, COL_MESSAGE, msg_item)

        spin = QSpinBox()
        spin.setRange(1, 1440)
        spin.setSuffix(" 분")
        spin.setValue(r.interval_min if r else 30)
        self.table.setCellWidget(row, COL_INTERVAL, spin)

        delete_btn = QPushButton("✕")
        delete_btn.setToolTip("삭제")
        delete_btn.setFixedWidth(24)
        existing_id = r.id if r else None
        delete_btn.clicked.connect(
            lambda _, b=delete_btn: self._on_delete_row(b, existing_id)
        )
        self.table.setCellWidget(row, COL_DELETE, delete_btn)

        if existing_id is not None:
            name_item.setData(Qt.UserRole, existing_id)

    def _on_add_row(self) -> None:
        self._append_row(None)
        new_row = self.table.rowCount() - 1
        self.table.setCurrentCell(new_row, COL_NAME)
        self.table.editItem(self.table.item(new_row, COL_NAME))

    def _on_delete_row(self, button: QPushButton, existing_id: int | None) -> None:
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, COL_DELETE) is button:
                self.table.removeRow(row)
                if existing_id is not None:
                    self._deleted_ids.add(existing_id)
                return

    def _read_row(self, row: int) -> Reminder:
        enabled_widget = self.table.cellWidget(row, COL_ENABLED)
        cb = enabled_widget.findChild(QCheckBox)
        spin = self.table.cellWidget(row, COL_INTERVAL)
        name_item = self.table.item(row, COL_NAME)
        msg_item = self.table.item(row, COL_MESSAGE)
        existing_id = name_item.data(Qt.UserRole) if name_item else None
        return Reminder(
            id=existing_id if isinstance(existing_id, int) else None,
            name=(name_item.text() if name_item else "").strip() or "이름 없음",
            message=(msg_item.text() if msg_item else "").strip() or "...",
            interval_min=int(spin.value()),
            enabled=bool(cb.isChecked()),
            last_fired_at=time.time(),
        )

    def _on_save(self) -> None:
        for rid in self._deleted_ids:
            self.store.delete_reminder(rid)
        self._deleted_ids.clear()

        existing = {r.id: r for r in self.store.list_reminders()}

        for row in range(self.table.rowCount()):
            r = self._read_row(row)
            if r.id is not None and r.id in existing:
                old = existing[r.id]
                r.last_fired_at = old.last_fired_at
            self.store.upsert_reminder(r)

        self.saved.emit()
