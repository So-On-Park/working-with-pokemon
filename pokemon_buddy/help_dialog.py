"""Read-only dialog summarising every feature so new users can find
their way around without poking at every menu item."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
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


SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    ("🐾 펫과 상호작용", [
        ("좌클릭", "쓰다듬기 — 친밀도 +1"),
        ("우클릭", "행동 메뉴 (밥 / 놀이 / 훈련 / 상세 / 내 포켓몬 / 내 가방 / 도감 / 이름 변경)"),
        ("드래그", "원하는 위치로 이동 — 자동 저장"),
        ("열린 채로 시간", "15분마다 EXP·친밀도 자동 적립 (잠금 화면 시 정지)"),
    ]),
    ("⚔️ 행동", [
        ("밥 주기 🍎", "친밀도 ↑. 일부 음식은 가방 인벤토리에서 소모"),
        ("놀아주기 🎯", "EXP +15, 친밀도 ↑"),
        ("훈련 💪", "EXP +35, 친밀도 ↑"),
        ("레벨업", "레벨이 오르면 자동 효과 + 일부 종은 진화 가능"),
    ]),
    ("🌳 야생 인카운터", [
        ("자동 등장", "5분마다 30% 확률로 화면에 야생 포켓몬 출현"),
        ("레어 변종 ✨", "1% 확률로 빛나는 레어 — 파티원 머리 위에 별 폭죽!"),
        ("잡기", "야생 포켓몬 클릭 → 75% 확률로 캐치, 실패시 도망"),
        ("커스텀 포켓몬", "직접 등록한 커스텀도 야생 풀에 자동 합류 (레어 변종은 없음)"),
    ]),
    ("🎒 아이템", [
        ("자동 드롭", "90초마다 화면에 사과·장난감·몬스터볼이 떨어짐"),
        ("수집", "떨어진 아이템 클릭 → 가방 추가"),
        ("특수 아이템", "물약(친밀도 ↑) / 진화석 / 마스터볼 — 가방 → 내 가방 → 사용"),
        ("적용 대상", "파티가 2마리 이상이면 누구에게 쓸지 선택 가능 (마스터볼 제외)"),
    ]),
    ("👥 파티 관리", [
        ("최대 3마리", "동시에 데스크탑에 띄울 수 있는 친구 수"),
        ("⭐ 추가 / ✓ 제외", "내 포켓몬 카드의 첫 버튼 — 파티 토글"),
        ("👑 대표로 설정", "파티원 중 한 마리를 슬롯 0(대표)로 승격. 트레이 아이콘도 그 모습"),
        ("📋 상세 정보", "잡힌 날짜, 친밀도, 표시 크기 배율 등 — 카드의 ✏️ 옆 또는 우클릭 메뉴에서"),
    ]),
    ("✨ 커스텀 포켓몬", [
        ("등록", "트레이 → '커스텀 포켓몬 추가…' → 이름 + GIF 선택"),
        ("권장 GIF", "128×128, 24~28 frames, 1MB 이하 (큰 파일은 펫이 무거워짐)"),
        ("표시 크기", "캐릭터 형상에 따라 자동으로 작아 보이면 배율로 보정"),
        ("스타일", "BW(도트) / 쇼다운 — 트레이 메뉴 → 스타일에서 토글. 기본은 쇼다운"),
    ]),
    ("📅 일정 + 리마인더", [
        ("일일 인사", "출근(9시) / 점심(12시) / 퇴근(18시) — 평일에만 자동 발화"),
        ("리마인더", "트레이 → 리마인더 설정 — 자유 시각 + 메시지"),
        ("일정", "트레이 → 일정 설정 — 출퇴근 시간 직접 조정"),
    ]),
]


class HelpDialog(QDialog):
    """Scrollable feature reference."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pokemon Buddy — 기능 설명")
        self.setMinimumSize(520, 600)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 8)

        title = QLabel("Pokemon Buddy 사용 안내")
        tf = QFont(); tf.setBold(True); tf.setPointSize(15)
        title.setFont(tf)
        root.addWidget(title)

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
