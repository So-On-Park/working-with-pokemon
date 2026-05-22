"""Dialog for registering a user-created Pokemon.

The user supplies a Korean display name and a base GIF. An optional "추가
모션" GIF can be uploaded too — it's saved but currently unused; the slot
exists so we can wire it up to a specific action animation later without
re-registering. On accept, BuddyApp hands the chosen paths to
`custom_pokemon.add()`."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap


log = logging.getLogger(__name__)
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


PREVIEW_SIDE = 96


class _GifSlot(QWidget):
    """File-picker row with a static first-frame preview. Holds the chosen
    path so the parent dialog can read it back on accept. We use a static
    QPixmap rather than QMovie because animated previews have been seen
    to wedge the dialog event loop on certain GIFs."""

    def __init__(self, label: str, required: bool,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.path: Optional[Path] = None

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self.preview = QLabel()
        self.preview.setFixedSize(PREVIEW_SIDE, PREVIEW_SIDE)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet(
            "border: 1px dashed #bbb; background: #fafafa; color: #888;"
        )
        self.preview.setText("미선택")
        row.addWidget(self.preview)

        right = QVBoxLayout()
        right.setSpacing(4)

        title = QLabel(label + (" *" if required else " (선택)"))
        title.setStyleSheet("font-weight: bold;")
        right.addWidget(title)

        self.path_label = QLabel("아직 파일 없음")
        self.path_label.setStyleSheet("color: #666; font-size: 8pt;")
        self.path_label.setWordWrap(True)
        right.addWidget(self.path_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        choose = QPushButton("파일 선택…")
        choose.clicked.connect(self._on_choose)
        btn_row.addWidget(choose)
        clear = QPushButton("지우기")
        clear.clicked.connect(self._clear)
        btn_row.addWidget(clear)
        btn_row.addStretch(1)
        right.addLayout(btn_row)
        right.addStretch(1)

        row.addLayout(right, stretch=1)

    def _on_choose(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "GIF 선택", "", "Animated GIF (*.gif)"
        )
        if not path:
            return
        self._set_path(Path(path))

    def _set_path(self, p: Path) -> None:
        self.path = p
        size_mb = p.stat().st_size / (1024 * 1024)
        self.path_label.setText(f"{p.name}  ({size_mb:.1f} MB)")
        # Static first-frame preview — no animation, no decoder loop, no
        # chance of wedging the dialog.
        pixmap = QPixmap(str(p))
        if pixmap.isNull():
            self.preview.setPixmap(QPixmap())
            self.preview.setStyleSheet(
                "border: 1px dashed #c47b1c; background: #fff8e8;"
                "color: #c47b1c; font-size: 8pt;"
            )
            self.preview.setText("미리보기\n불가")
            return
        scaled = pixmap.scaled(
            self.preview.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.preview.setText("")
        self.preview.setStyleSheet(
            "border: 1px solid #ccc; background: #fafafa;"
        )
        self.preview.setPixmap(scaled)

    def _clear(self) -> None:
        self.path = None
        self.preview.setPixmap(QPixmap())
        self.preview.setStyleSheet(
            "border: 1px dashed #bbb; background: #fafafa; color: #888;"
        )
        self.preview.setText("미선택")
        self.path_label.setText("아직 파일 없음")


class CustomPokemonDialog(QDialog):
    """Collects the data needed to register a new custom Pokemon. The dialog
    only gathers user input — actual file copy + registry write happens in
    the BuddyApp handler once `accept()` succeeds."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("커스텀 포켓몬 추가")
        self.setMinimumWidth(420)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        # NOTE: deliberately NOT calling setWindowModality(ApplicationModal).
        # PySide6 has been observed to leave exec() hanging when both an
        # explicit modality is set AND the dialog uses exec(). exec()'s
        # own modal loop is sufficient — buddies are hidden by the caller
        # so there's nothing else to click anyway.

        root = QVBoxLayout(self)
        root.setSpacing(10)

        intro = QLabel(
            "직접 만든 GIF를 새로운 포켓몬으로 등록할 수 있어. "
            "기본 GIF는 필수, 추가 모션은 선택이야 (지금은 보관만 됨). "
            "권장 크기: 1MB 이하 (큰 파일은 펫이 무거워져)."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #555; font-size: 9pt;")
        root.addWidget(intro)

        form = QFormLayout()
        form.setSpacing(6)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("예) 마이몬")
        form.addRow("이름 (한글) *", self.name_input)

        self.eng_input = QLineEdit()
        self.eng_input.setPlaceholderText("선택 — 도감/내부용 영문 ID")
        form.addRow("영문 ID", self.eng_input)

        self.scale_input = QDoubleSpinBox()
        self.scale_input.setRange(0.5, 2.5)
        self.scale_input.setSingleStep(0.1)
        self.scale_input.setDecimals(2)
        self.scale_input.setValue(1.0)
        self.scale_input.setToolTip(
            "캐릭터가 화면에서 작아 보이면 1.3~1.6, 너무 크면 0.7~0.9. 기본 1.0."
        )
        form.addRow("표시 크기 배율", self.scale_input)

        root.addLayout(form)

        self.base_slot = _GifSlot("기본 GIF", required=True)
        root.addWidget(self.base_slot)

        self.extra_slot = _GifSlot("추가 모션 GIF", required=False)
        root.addWidget(self.extra_slot)

        self.warning = QLabel("")
        self.warning.setStyleSheet("color: #c0392b; font-size: 9pt;")
        self.warning.setWordWrap(True)
        root.addWidget(self.warning)

        # Plain QPushButtons wired to clicked — QDialogButtonBox.accepted
        # was suspected of not firing reliably for one user, so this removes
        # that abstraction.
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        add_btn = QPushButton("추가")
        add_btn.setDefault(True)
        add_btn.clicked.connect(self._on_accept)
        button_row.addWidget(add_btn)
        root.addLayout(button_row)

    # ---- accessors for the caller after exec() ----
    @property
    def name_ko(self) -> str:
        return self.name_input.text().strip()

    @property
    def name_eng(self) -> Optional[str]:
        text = self.eng_input.text().strip()
        return text or None

    @property
    def base_path(self) -> Optional[Path]:
        return self.base_slot.path

    @property
    def extra_path(self) -> Optional[Path]:
        return self.extra_slot.path

    @property
    def display_scale(self) -> float:
        return float(self.scale_input.value())

    # ---- lifecycle ----
    def showEvent(self, ev) -> None:  # noqa: N802
        super().showEvent(ev)
        # Force foreground — the buddy windows are Qt.WindowStaysOnTopHint
        # and otherwise the dialog can render behind them in some setups.
        self.raise_()
        self.activateWindow()

    # ---- validation ----
    def _on_accept(self) -> None:
        log.debug(
            "CustomPokemonDialog._on_accept ENTRY name_ko=%r base=%s extra=%s",
            self.name_ko,
            str(self.base_path) if self.base_path else None,
            str(self.extra_path) if self.extra_path else None,
        )
        self.warning.setStyleSheet("color: #2980b9; font-size: 9pt;")
        self.warning.setText(
            f"검증 중… 이름={'O' if self.name_ko else 'X'} "
            f"기본={'O' if self.base_path else 'X'} "
            f"추가={'O' if self.extra_path else '-'}"
        )
        if not self.name_ko:
            log.debug("  reject: name empty")
            self.warning.setStyleSheet("color: #c0392b; font-size: 9pt;")
            self.warning.setText("이름을 입력해줘.")
            return
        if self.base_path is None:
            log.debug("  reject: base_path None")
            self.warning.setStyleSheet("color: #c0392b; font-size: 9pt;")
            self.warning.setText("기본 GIF는 필수야.")
            return
        base_exists = self.base_path.exists()
        log.debug("  base_path.exists()=%s", base_exists)
        if not base_exists:
            log.debug("  reject: base_path missing on disk")
            self.warning.setStyleSheet("color: #c0392b; font-size: 9pt;")
            self.warning.setText(f"기본 GIF 못 찾음: {self.base_path}")
            return
        if self.extra_path is not None:
            extra_exists = self.extra_path.exists()
            log.debug("  extra_path.exists()=%s", extra_exists)
            if not extra_exists:
                log.debug("  reject: extra_path missing on disk")
                self.warning.setStyleSheet("color: #c0392b; font-size: 9pt;")
                self.warning.setText(f"추가 GIF 못 찾음: {self.extra_path}")
                return
        log.debug("  all checks passed, calling self.done(Accepted)")
        # done() is slightly lower-level than accept() and ends the exec()
        # loop more deterministically in PySide6.
        self.done(QDialog.Accepted)
        log.debug("  self.done() returned")
