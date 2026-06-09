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
    ("🐾 펫과 상호작용", [
        ("좌클릭", "친구를 쓰다듬어줘 — 친밀도가 올라가"),
        ("우클릭", "행동 메뉴 (밥 / 놀이 / 훈련 / 상세 / 내 포켓몬 / 내 가방 / 도감 / 이름 변경)"),
        ("드래그", "원하는 위치로 이동 — 다음에도 그 자리에 있어"),
        ("함께 있는 시간", "꾸준히 함께 있으면 천천히 EXP와 친밀도가 올라가"),
    ]),
    ("⚔️ 행동", [
        ("밥 주기 🍎", "친밀도 올림. 가방에 음식이 있으면 그걸 줘"),
        ("놀아주기 🎯", "EXP + 친밀도 올림"),
        ("훈련 💪", "더 많은 EXP + 친밀도"),
        ("레벨업", "레벨이 오르면 화려한 효과! 일부 종은 진화할 수 있어"),
    ]),
    ("🌳 야생 친구 만나기", [
        ("등장", "가끔 화면 어딘가에 야생 포켓몬이 나타나"),
        ("레어 ✨", "운이 좋으면 빛나는 레어 변종 — 파티원 머리 위에 별이 터져!"),
        ("잡기", "야생 친구를 클릭하면 몬스터볼을 던져. 가끔 도망가기도 해"),
        ("커스텀 포켓몬", "직접 등록한 친구도 야생에서 만날 수 있어"),
    ]),
    ("🎒 아이템", [
        ("아이템 드롭", "화면에 사과·장난감·몬스터볼이 떨어져 — 클릭해서 줍기 (잠깐 머물다 사라져)"),
        ("특수 아이템", "물약, 진화석, 마스터볼 같은 것들 — 트레이 → 내 가방 → 사용"),
        ("적용 대상", "파티가 여러 마리면 누구에게 쓸지 선택할 수 있어"),
        ("표시 켜기/끄기", "트레이 → '화면 아이템 표시'로 드롭을 끄고 켤 수 있어 (가방은 그대로)"),
    ]),
    ("🎁 포켓몬 보내기 / 불러오기", [
        ("보내기", "상세보기 → '보내기'로 포켓몬을 파일(.pokeball)로 내보내 친구에게 전달 (보내면 내 가방에선 사라져)"),
        ("불러오기", "트레이 → '포켓몬/스킬 불러오기' 또는 파일 더블클릭 → 두근두근 연출과 함께 합류"),
        ("종 파일", "pokeballs 폴더의 종(species) 파일을 불러오면 새로 잡은 것처럼 등장 (레벨1·랜덤)"),
        ("스킬 보내기", "가방의 기술 교본을 '보내기'로 .scroll 파일로 — 불러오면 교본을 받아"),
    ]),
    ("📜 기술 (스킬)", [
        ("기술 교본", "아주 가끔 두루마리(📜)가 떨어져 — 주워서 내 가방에 보관"),
        ("전수", "내 가방 → 교본의 '전수' 버튼으로 파티원에게 기술을 가르쳐"),
        ("유대로 습득", "친밀도가 100인 친구는 레벨업할 때 스스로 기술을 깨우쳐"),
        ("수집광", "이 기술을 지닌 친구는 화면에 떨어진 아이템을 끌어당겨 자동으로 주워와"),
    ]),
    ("👥 파티 관리", [
        ("최대 3마리", "동시에 데스크탑에 띄울 수 있는 친구 수"),
        ("⭐ 추가 / ✓ 제외", "내 포켓몬 카드의 첫 버튼 — 파티 토글"),
        ("👑 대표로 설정", "파티원 중 한 마리를 대표로 승격. 트레이 아이콘도 그 모습"),
        ("📋 상세 정보", "잡힌 날짜, 친밀도, 표시 크기 배율 등을 볼 수 있어"),
    ]),
    ("✨ 커스텀 포켓몬", [
        ("등록", "트레이 → '커스텀 포켓몬 추가…' → 이름 + GIF 선택"),
        ("권장 GIF", "128×128 크기, 1MB 이하 (큰 파일은 펫이 무거워져)"),
        ("표시 크기", "캐릭터가 너무 작거나 크면 배율로 조정"),
        ("스타일", "BW(도트) / 쇼다운 — 트레이 메뉴 → 스타일에서 토글"),
    ]),
    ("🔔 리마인더", [
        ("등록", "트레이 → 리마인더 설정 — 시각 + 메시지를 자유롭게"),
        ("동작", "지정한 시각에 친구가 알림을 띄워줘"),
    ]),
    ("🛠️ 기타", [
        ("모험자 이름 변경", "트레이 → 모험자 이름 변경 — 친구가 가끔 이름을 불러줘"),
        ("초기화", "트레이 → 초기화 — 처음부터 다시 시작 (모든 진행도 사라짐)"),
    ]),
    ("📜 저작권 · 크레딧", [
        ("비영리 팬 프로젝트", "Nintendo·Game Freak·The Pokémon Company와 제휴·후원 관계가 없어"),
        ("포켓몬 저작권", "포켓몬·이름·스프라이트의 권리는 The Pokémon Company / Nintendo에 있어"),
        ("스프라이트 출처", "PokéAPI(CC0) · Pokémon Showdown/Smogon(출처 표기). 자세한 건 CREDITS.md"),
        ("커스텀 포켓몬", "9000번대 커스텀 GIF는 사용자가 직접 만든 창작물"),
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
        self.setMinimumSize(520, 600)
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
        tf = QFont(); tf.setBold(True); tf.setPointSize(15)
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

        subtitle = QLabel(
            "데스크탑 위에서 친구가 살아 움직여. "
            "원할 때 우클릭 + 트레이 메뉴로 모든 기능에 접근할 수 있어."
        )
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
        note = QLabel(
            "더 궁금한 점은 README.md 또는 debug.log를 참고해줘. "
            "버그가 보이면 그 로그를 첨부해서 알려주면 큰 도움이 돼!"
        )
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
            k.setFixedWidth(110)
            k.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            row.addWidget(k)
            v = QLabel(desc)
            v.setWordWrap(True)
            v.setStyleSheet("color: #222; font-size: 9pt;")
            row.addWidget(v, stretch=1)
            layout.addLayout(row)
        return w
