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

from . import theme
from .pokeball import make_pokeball_pixmap


# Number of consecutive clicks on the pokéball that toggles developer mode.
DEV_MODE_CLICKS = 10
BALL_HEADER_PX = 36


SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    ("🐾 기본 조작", [
        ("좌클릭", "쓰다듬기. 친밀도가 조금씩 오릅니다"),
        ("드래그", "원하는 자리로 옮기기"),
        ("우클릭", "밥 주기부터 도감, 설정까지 모든 메뉴"),
    ]),
    ("💛 키우기", [
        ("자동 성장", "화면에 띄워두면 15분마다 경험치가 쌓입니다"),
        ("만렙까지", "화면 시간 기준 약 3주. 직접 챙기면 더 빨라집니다"),
        ("밥, 놀이, 훈련", "경험치는 훈련이 가장 많고 밥이 가장 적습니다"),
        ("친밀도", "60부터 경험치에 보너스. 높을수록 많이 받습니다"),
        ("진화", "조건을 채우면 한 번 물어봅니다. 미루면 상세 창에서 언제든"),
    ]),
    ("🌳 야생과 도감", [
        ("야생 포켓몬", "가끔 화면에 나타납니다. 클릭해서 몬스터볼로 포획"),
        ("이로치 ✨", "색이 다른 희귀 개체. 도감에 별도로 기록됩니다"),
    ]),
    ("🎒 아이템과 스킬", [
        ("줍기", "화면에 떨어진 아이템을 클릭하면 가방으로"),
        ("사용", "내 가방에서 특수 아이템 사용, 스킬 전수"),
        ("수집광", "친밀도 100에서 스스로 익힙니다. 아이템을 자동으로 주워옵니다"),
        ("명포수", "레벨 100에서 익힙니다. 야생을 알아서 포획합니다"),
    ]),
    ("🎁 주고받기", [
        ("보내기", "포켓몬과 스킬을 파일 하나로 내보냅니다"),
        ("받기", "받은 파일을 더블클릭하면 바로 합류"),
    ]),
    ("👥 파티", [
        ("세 마리까지", "화면에 함께 둘 수 있습니다. 가득 차면 교체 대상을 고르면 됩니다"),
        ("대표 👑", "맨 앞자리 포켓몬이 트레이 아이콘이 됩니다"),
    ]),
    ("🎨 꾸미기", [
        ("색상 테마", "스타터 네 종류. 고르면 앱 전체 색이 바뀝니다"),
        ("커스텀 포켓몬", "GIF 파일로 새 포켓몬 등록 (128×128 권장)"),
        ("표시 크기", "상세 창에서 최대 3배까지"),
    ]),
    ("🔕 방해 금지", [
        ("조용히 시키기", "말풍선만 멈춥니다. 성장은 그대로 이어집니다"),
        ("화면에서 숨기기", "화면을 캡쳐할 때 잠시 숨겨둘 수 있습니다"),
        ("자리 정렬", "흩어진 포켓몬을 오른쪽 아래로 다시 정렬"),
    ]),
    ("🔔 그 밖에", [
        ("리마인더", "물 마시기 같은 일정을 정해두면 때맞춰 알려줍니다"),
        ("백업", "지금까지의 진행도를 저장하고 되돌릴 수 있습니다"),
    ]),
    ("📜 저작권", [
        ("팬 프로젝트", "비영리로 만들었습니다. Nintendo, Game Freak, "
                    "포켓몬 컴퍼니와 무관 (출처는 CREDITS.md)"),
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
        title = QLabel("기능 안내")
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
            f"QPushButton:hover {{ background: {theme.primary_rgba(30)};"
            "  border-radius: 22px; }"
        )
        self._ball_btn.setToolTip("Pokemon Buddy")
        self._ball_btn.clicked.connect(self._on_ball_clicked)
        title_row.addWidget(self._ball_btn)

        root.addLayout(title_row)

        subtitle = QLabel("포켓몬 우클릭 또는 트레이 아이콘에서 "
                          "대부분의 기능을 찾을 수 있습니다 ✨")
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
        note = QLabel("문제가 생기면 debug.log와 함께 알려주세요. "
                      "나머지 설명은 README에 있습니다")
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
            f"color: {theme.on_primary()}; background: {theme.primary()};"
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
            f"color: {theme.on_primary()}; background: {theme.primary()};"
            "padding: 4px 10px; border-radius: 4px;"
        )
        layout.addWidget(head)

        for key, desc in entries:
            row = QHBoxLayout()
            row.setSpacing(8)
            row.setContentsMargins(8, 0, 0, 0)
            k = QLabel(key)
            k.setStyleSheet(
                f"color: {theme.primary()}; font-weight: bold; font-size: 9pt;"
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
