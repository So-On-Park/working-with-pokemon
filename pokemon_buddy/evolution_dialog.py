"""Evolution prompt — before/after sprites with yes/no buttons."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QImageReader, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .pet_window import _scaled_pixmap, _placeholder_pixmap


def _first_frame(path: Optional[Path], side: int) -> QPixmap:
    if path is None or not Path(path).exists():
        return _placeholder_pixmap(side)
    suffix = Path(path).suffix.lower()
    if suffix == ".gif":
        reader = QImageReader(str(path))
        if reader.canRead():
            img = reader.read()
            if not img.isNull():
                pm = QPixmap.fromImage(img)
                return pm.scaled(side, side, Qt.KeepAspectRatio,
                                 Qt.FastTransformation
                                 if max(pm.width(), pm.height()) <= 96
                                 else Qt.SmoothTransformation)
    return _scaled_pixmap(Path(path), side)


class EvolutionDialog(QDialog):
    SPRITE_SIDE = 110

    def __init__(self, before_name: str, after_name: str,
                 before_path: Optional[Path], after_path: Optional[Path],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("진화")
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setMinimumWidth(360)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(10)

        title = QLabel(f"? {before_name}가(이) 진화하려고 한다!")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        # Sprites side-by-side with an arrow between
        sprite_row = QHBoxLayout()
        sprite_row.setSpacing(8)
        sprite_row.setAlignment(Qt.AlignCenter)

        before_label = QLabel()
        before_label.setPixmap(_first_frame(before_path, self.SPRITE_SIDE))
        before_label.setAlignment(Qt.AlignCenter)
        sprite_row.addWidget(before_label)

        arrow = QLabel("→")
        arrow_font = QFont()
        arrow_font.setPointSize(28)
        arrow_font.setBold(True)
        arrow.setFont(arrow_font)
        arrow.setStyleSheet("color: #4a7ddc;")
        arrow.setAlignment(Qt.AlignCenter)
        sprite_row.addWidget(arrow)

        after_label = QLabel()
        after_label.setPixmap(_first_frame(after_path, self.SPRITE_SIDE))
        after_label.setAlignment(Qt.AlignCenter)
        sprite_row.addWidget(after_label)

        root.addLayout(sprite_row)

        names_row = QHBoxLayout()
        names_row.setSpacing(8)
        names_row.setAlignment(Qt.AlignCenter)
        before_n = QLabel(before_name); before_n.setAlignment(Qt.AlignCenter)
        before_n.setFixedWidth(self.SPRITE_SIDE)
        after_n = QLabel(after_name); after_n.setAlignment(Qt.AlignCenter)
        after_n.setFixedWidth(self.SPRITE_SIDE)
        spacer = QLabel(""); spacer.setFixedWidth(40)
        names_row.addWidget(before_n)
        names_row.addWidget(spacer)
        names_row.addWidget(after_n)
        root.addLayout(names_row)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        no_btn = QPushButton("나중에")
        no_btn.clicked.connect(self.reject)
        btn_row.addWidget(no_btn)

        yes_btn = QPushButton("진화시키기!")
        yes_btn.setDefault(True)
        yes_btn.setStyleSheet(
            "QPushButton { background: #4a7ddc; color: white; "
            "  padding: 6px 14px; border-radius: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #3a6ac0; }"
        )
        yes_btn.clicked.connect(self.accept)
        btn_row.addWidget(yes_btn)
        root.addLayout(btn_row)
