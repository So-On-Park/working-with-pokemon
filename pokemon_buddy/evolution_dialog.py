"""Evolution prompt — before/after sprites with yes/no buttons.

Sprites render at their NATIVE size (1.0). They used to be blown up to a
fixed 110px box, which made the buddy look bigger in this dialog than it
does on the desktop. `SPRITE_BOX` is now only the layout slot / downscale
ceiling, never an upscale target.

If the evolved form isn't in the dex yet it shows as a black silhouette
with a "???" name — the reveal happens when the buddy actually evolves."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QImageReader, QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .pet_window import _scaled_pixmap, _placeholder_pixmap


UNKNOWN_NAME = "???"


def _first_frame(path: Optional[Path], box: int) -> QPixmap:
    """First frame at 1.0 scale. Only shrinks — never enlarges — so the
    sprite matches the size the user sees on their desktop."""
    if path is None or not Path(path).exists():
        return _placeholder_pixmap(box)
    p = Path(path)
    pm: Optional[QPixmap] = None
    if p.suffix.lower() == ".gif":
        reader = QImageReader(str(p))
        if reader.canRead():
            img = reader.read()
            if not img.isNull():
                pm = QPixmap.fromImage(img)
    if pm is None:
        pm = _scaled_pixmap(p, box)
    if pm.isNull():
        return _placeholder_pixmap(box)
    # 1.0 unless it genuinely doesn't fit the slot.
    if pm.width() > box or pm.height() > box:
        return pm.scaled(box, box, Qt.KeepAspectRatio,
                         Qt.SmoothTransformation)
    return pm


def silhouette(pm: QPixmap) -> QPixmap:
    """Flatten every visible pixel to black, keeping the alpha channel —
    the dex "who's that Pokemon?" look."""
    if pm.isNull():
        return pm
    out = QPixmap(pm.size())
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.drawPixmap(0, 0, pm)
    # SourceIn paints the fill only where the sprite is already opaque.
    p.setCompositionMode(QPainter.CompositionMode_SourceIn)
    p.fillRect(out.rect(), QColor(0, 0, 0))
    p.end()
    return out


class EvolutionDialog(QDialog):
    SPRITE_BOX = 110          # layout slot + downscale ceiling (not a target)
    SPRITE_SIDE = SPRITE_BOX  # back-compat alias

    def __init__(self, before_name: str, after_name: str,
                 before_path: Optional[Path], after_path: Optional[Path],
                 parent: QWidget | None = None, *,
                 after_known: bool = True) -> None:
        super().__init__(parent)
        self.setWindowTitle("진화")
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setMinimumWidth(360)
        self.after_known = after_known

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(10)

        title = QLabel(f"✨ {before_name}가(이) 진화하려고 한다!")
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

        self._before_label = QLabel()
        self._before_label.setPixmap(_first_frame(before_path, self.SPRITE_BOX))
        self._before_label.setAlignment(Qt.AlignCenter)
        self._before_label.setFixedSize(self.SPRITE_BOX, self.SPRITE_BOX)
        sprite_row.addWidget(self._before_label)

        arrow = QLabel("→")
        arrow_font = QFont()
        arrow_font.setPointSize(28)
        arrow_font.setBold(True)
        arrow.setFont(arrow_font)
        arrow.setStyleSheet(f"color: {theme.primary()};")
        arrow.setAlignment(Qt.AlignCenter)
        sprite_row.addWidget(arrow)

        after_pm = _first_frame(after_path, self.SPRITE_BOX)
        if not after_known:
            after_pm = silhouette(after_pm)
        self._after_label = QLabel()
        self._after_label.setPixmap(after_pm)
        self._after_label.setAlignment(Qt.AlignCenter)
        self._after_label.setFixedSize(self.SPRITE_BOX, self.SPRITE_BOX)
        if not after_known:
            self._after_label.setToolTip("도감에 없는 포켓몬이야. 진화시키면 밝혀져!")
        sprite_row.addWidget(self._after_label)

        root.addLayout(sprite_row)

        names_row = QHBoxLayout()
        names_row.setSpacing(8)
        names_row.setAlignment(Qt.AlignCenter)
        before_n = QLabel(before_name); before_n.setAlignment(Qt.AlignCenter)
        before_n.setFixedWidth(self.SPRITE_BOX)
        # A named silhouette defeats the point — hide the name with it.
        self.after_label_text = after_name if after_known else UNKNOWN_NAME
        after_n = QLabel(self.after_label_text)
        after_n.setAlignment(Qt.AlignCenter)
        after_n.setFixedWidth(self.SPRITE_BOX)
        if not after_known:
            after_n.setStyleSheet("color: #888; font-weight: bold;")
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
            f"QPushButton {{ background: {theme.primary()};"
            f"  color: {theme.on_primary()};"
            "  padding: 6px 14px; border-radius: 6px; font-weight: bold; }"
            f"QPushButton:hover {{ background: {theme.primary_dark()}; }}"
        )
        yes_btn.clicked.connect(self.accept)
        btn_row.addWidget(yes_btn)
        root.addLayout(btn_row)
