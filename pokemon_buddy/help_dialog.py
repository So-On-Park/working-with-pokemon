"""Read-only dialog summarising every feature so new users can find
their way around without poking at every menu item."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .pokeball import make_pokeball_pixmap


# Number of consecutive clicks on the pokéball that toggles developer mode.
DEV_MODE_CLICKS = 10
BALL_HEADER_PX = 36


SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    ("🐾 기본 조작", [
        ("좌클릭 · 드래그", "쓰다듬기(친밀도↑) · 원하는 곳으로 이동"),
        ("우클릭", "행동 · 내 포켓몬 · 가방 · 도감 등 모든 메뉴"),
    ]),
    ("💛 키우기", [
        ("밥 · 놀이 · 훈련", "EXP·친밀도가 올라가 (함께 있기만 해도 천천히↑)"),
        ("레벨업 · 진화", "약 2주 함께하면 만렙 — 일부는 진화해"),
    ]),
    ("🌳 야생 · 도감", [
        ("포획", "가끔 나타나는 야생을 클릭해 몬스터볼로 잡기"),
        ("레어 ✨", "아주 가끔 빛나는 레어가 등장 — 도감을 채워봐"),
    ]),
    ("🎒 아이템 · 기술", [
        ("줍기", "화면에 떨어진 아이템을 클릭해 가방에 보관"),
        ("사용 · 전수", "트레이 → 내 가방에서 특수아이템 사용 · 교본 전수"),
        ("수집광", "친밀도 100이면 깨우치는 기술 — 아이템 자동 수집"),
    ]),
    ("🎁 보내기 · 불러오기", [
        ("파일로 공유", "포켓몬·기술을 파일로 내보내고, 받은 파일은 더블클릭으로 합류"),
    ]),
    ("👥 파티 · 커스텀", [
        ("최대 3마리", "내 포켓몬에서 파티 토글 · 👑 대표 설정"),
        ("커스텀 포켓몬", "트레이 → 추가 → 이름 + GIF (128×128 권장)"),
    ]),
    ("🔔 그 외", [
        ("리마인더", "트레이 → 리마인더로 시각·메시지 알림 등록"),
        ("이름 변경 · 초기화", "트레이 메뉴에서"),
    ]),
    ("📜 저작권", [
        ("비영리 팬 프로젝트", "Nintendo·Game Freak·TPC와 무관 · 출처는 CREDITS.md"),
    ]),
]


class HelpDialog(QDialog):
    """Scrollable feature reference.

    The pokéball next to the title is a secret toggle — clicking it
    `DEV_MODE_CLICKS` times in a single dialog session flips developer
    mode (the test-only tray menu items appear/disappear)."""

    developer_mode_toggled = Signal(bool)  # new state — caller rebuilds tray

    def __init__(self, store, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from . import __version__
        self.setWindowTitle(f"Pokemon Buddy v{__version__} — 기능 설명")
        self.setMinimumSize(440, 480)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        self.store = store
        self._ball_clicks = 0

        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 8)

        # Title row: title + secret pokéball toggle
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title = QLabel("Pokemon Buddy 사용 안내")
        tf = QFont(); tf.setBold(True); tf.setPointSize(12)
        title.setFont(tf)
        title_row.addWidget(title)
        title_row.addStretch(1)

        self._ball_btn = QPushButton()
        self._ball_btn.setIcon(QIcon(make_pokeball_pixmap(BALL_HEADER_PX)))
        self._ball_btn.setIconSize(QSize(BALL_HEADER_PX, BALL_HEADER_PX))
        self._ball_btn.setFixedSize(BALL_HEADER_PX + 8, BALL_HEADER_PX + 8)
        self._ball_btn.setFlat(True)
        self._ball_btn.setCursor(Qt.PointingHandCursor)
        self._ball_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; }"
            "QPushButton:hover { background: rgba(74,125,220,30);"
            "  border-radius: 22px; }"
        )
        self._ball_btn.setToolTip("Pokemon Buddy")
        self._ball_btn.clicked.connect(self._on_ball_clicked)
        title_row.addWidget(self._ball_btn)

        root.addLayout(title_row)

        subtitle = QLabel("우클릭과 트레이 메뉴에 모든 기능이 들어 있어 ✨")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #666; font-size: 9pt;")
        root.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(14)
        inner_layout.setContentsMargins(2, 6, 2, 6)

        for heading, entries in SECTIONS:
            inner_layout.addWidget(self._build_section(heading, entries))

        # Closing note
        note = QLabel("자세한 내용은 README.md · 버그는 debug.log와 함께 알려줘!")
        note.setWordWrap(True)
        note.setStyleSheet("color: #888; font-size: 9pt; padding: 6px 2px;")
        inner_layout.addWidget(note)
        inner_layout.addStretch(1)

        scroll.setWidget(inner)
        root.addWidget(scroll, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        close = QPushButton("닫기")
        close.setFixedSize(72, 28)
        close.clicked.connect(self.accept)
        btn_row.addWidget(close)
        root.addLayout(btn_row)

    def _on_ball_clicked(self) -> None:
        self._ball_clicks += 1
        if self._ball_clicks < DEV_MODE_CLICKS:
            return
        # Threshold hit — flip developer mode in the store and let the
        # caller refresh its tray menu.
        self._ball_clicks = 0
        current = self.store.get_meta("developer_mode") == "1"
        new_state = not current
        self.store.set_meta("developer_mode", "1" if new_state else "0")
        # Visual confirmation right inside the dialog so the user knows
        # the secret tap was recognised.
        toast = QLabel(
            f"🛠️ 개발자 모드 {'ON' if new_state else 'OFF'}"
        )
        toast.setStyleSheet(
            "color: white; background: #4a7ddc;"
            "border-radius: 6px; padding: 6px 12px;"
            "font-weight: bold; font-size: 11pt;"
        )
        toast.setAlignment(Qt.AlignCenter)
        # Insert at the top of the root layout so it's immediately visible.
        self.layout().insertWidget(0, toast)
        # Auto-remove the toast after a few seconds so it doesn't stick.
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2500, toast.deleteLater)
        self.developer_mode_toggled.emit(new_state)

    @staticmethod
    def _build_section(heading: str, entries: list[tuple[str, str]]) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)

        head = QLabel(heading)
        hf = QFont(); hf.setBold(True); hf.setPointSize(11)
        head.setFont(hf)
        head.setStyleSheet(
            "color: white; background: #4a7ddc;"
            "padding: 4px 10px; border-radius: 4px;"
        )
        layout.addWidget(head)

        for key, desc in entries:
            row = QHBoxLayout()
            row.setSpacing(8)
            row.setContentsMargins(8, 0, 0, 0)
            k = QLabel(key)
            k.setStyleSheet(
                "color: #4a7ddc; font-weight: bold; font-size: 9pt;"
            )
            k.setFixedWidth(124)
            k.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            row.addWidget(k)
            v = QLabel(desc)
            v.setWordWrap(True)
            v.setStyleSheet("color: #222; font-size: 9pt;")
            row.addWidget(v, stretch=1)
            layout.addLayout(row)
        return w
