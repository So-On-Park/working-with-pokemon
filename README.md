# Pokemon Buddy

데스크탑 위에서 살아 움직이는 포켓몬 친구. 우클릭으로 밥 주고, 놀아주고, 훈련시키며 함께 일하는 작은 펫 앱.

![status](https://img.shields.io/badge/platform-Windows-blue) ![python](https://img.shields.io/badge/python-3.11%2B-green)

## 주요 기능

- **파티 3마리까지** — 데스크탑에 동시에 띄울 수 있는 동료
- **친밀도 + 경험치** — 함께한 시간이 쌓이면 레벨업 + 친밀도 상승, 진화 가능
- **야생 인카운터** — 화면에 야생 포켓몬이 등장, 클릭해서 잡기. 가끔 레어 변종도 나옴
- **아이템 시스템** — 가방에 떨어진 사과/장난감/몬스터볼 수집, 진화석 사용
- **도감 + 가방** — Gen 1 + 사용자가 만든 커스텀까지 일관된 UI로 관리
- **커스텀 포켓몬 등록** — 직접 그린 GIF로 나만의 종 추가 (자동으로 야생 풀에도 합류)
- **모험자 이름** — 첫 실행 시 이름을 정하면 친구가 가끔 불러줘. 트레이 메뉴에서 언제든 변경
- **리마인더** — 사용자가 원하는 시각·메시지 자유 설정
- **두 가지 스프라이트 스타일** — BW 도트 / 쇼다운 애니메이션 토글

## 요구사항

- **Windows 10/11**
- **Python 3.11+** (3.14 권장)
- 인터넷 연결 (PokeAPI 첫 fetch — 캐시 후엔 오프라인 동작)

## 설치

```cmd
git clone <REPO_URL> pokemon-buddy
cd pokemon-buddy
python -m venv .venv --copies
.venv\Scripts\activate
pip install -r requirements.txt
```

> `--copies` 옵션은 venv launcher가 base Python을 자식 프로세스로 띄우는 동작을 피해 인스턴스가 1개만 떠도록 합니다.

## 실행

가장 간단한 방법:

```cmd
run.bat
```

종료:

```cmd
stop.bat
```

`run.bat`은 `pythonw.exe`로 띄워 콘솔 창 없이 시스템 트레이에서 동작합니다. 트레이 아이콘 우클릭 → "종료".

## 트레이 메뉴

| 항목 | 동작 |
|------|------|
| 밥 주기 / 놀아주기 / 훈련 | 친밀도·EXP 적립 |
| 이름 변경 | 포켓몬 닉네임 설정/해제 |
| 내 포켓몬 | 가방 + 파티 관리 |
| 내 가방 | 인벤토리 — 진화석·물약·마스터볼 사용 |
| 도감 | 잡은 포켓몬 컬렉션 |
| 리마인더 설정 | 사용자 알람 관리 |
| 모험자 이름 변경 | 친구가 부를 이름 변경 |
| 커스텀 포켓몬 추가 | GIF로 새 종 등록 |
| 기능 설명 | 모든 기능 한 눈에 |

## 커스텀 포켓몬 추가

1. **GIF 준비** — 권장 128×128, 1MB 이하. 큰 GIF는 함께 제공되는 `pokemon-maker/optimize_pokemon_gifs.py`로 자동 최적화 가능
2. 트레이 → **"커스텀 포켓몬 추가…"**
3. 이름(한글) + 기본 GIF + (선택) 추가 모션 + 표시 크기 배율 입력
4. **추가** 클릭 → 가방·도감·야생 풀에 동시 등록

등록된 포켓몬은 `assets/9001+_bw.gif` 등으로 저장되며 `assets/custom_pokemon.json`에 메타데이터가 기록됩니다.

## 테스트

```cmd
.venv\Scripts\python -m pytest tests/ -q
```

87개 테스트 — 약 5초 안에 통과. 자세한 종류는 `tests/test_*.py` 참고.

## 로깅

- **`debug.log`** (DEBUG 이상) — 시스템 동작 풀 트레이스. 버그 보고 시 마지막 ~50줄 첨부
- **콘솔** (INFO 이상) — 사용자 액션만. `pythonw.exe`에서는 출력 없음 (정상)

## 데이터 위치

| 경로 | 내용 | 이주 가능? |
|------|------|------------|
| `data/buddy.db` | 가방·도감·인벤토리·친밀도 등 모든 게임 상태 | 다른 PC로 복사 시 데이터 보존 |
| `assets/*.gif` | PokeAPI 캐시 + 커스텀 GIF | 다운로드 다시 받으면 자동 채워짐 |
| `assets/custom_pokemon.json` | 커스텀 포켓몬 메타 | 사용자 정의 — 따로 백업 권장 |
| `assets/display_scale.json` | per-dex 표시 크기 배율 | 사용자 정의 |
| `debug.log` | 런타임 로그 | 무시 가능 (재생성됨) |

## 라이선스 + 스프라이트 출처

- 스프라이트는 [PokeAPI/sprites](https://github.com/PokeAPI/sprites) (Gen 5 BW) + [Pokemon Showdown](https://play.pokemonshowdown.com/) — 각 프로젝트의 라이선스에 따름
- 커스텀 GIF는 사용자가 직접 제작/소유한 자산만 사용
- 본 프로젝트 코드: TBD (배포 시 LICENSE 추가)

## 문제 해결

| 증상 | 원인 / 해결 |
|------|------|
| 트레이에 아이콘이 안 보임 | Windows 11은 새 트레이 아이콘을 ^(오버플로) 안에 숨김 등록 → 설정에서 ON |
| 펫이 화면 밖으로 나감 | `stop.bat` 후 좌표 reset: `python -c "from pokemon_buddy.state import Store; s=Store(); s.conn.execute(\"DELETE FROM meta WHERE key LIKE 'win_%'\"); s.conn.commit()"` |
| `pythonw.exe` 프로세스 2개 보임 | venv launcher + base interpreter 한 쌍. 실제 인스턴스는 1개 — 정상 |
| 커스텀 추가 다이얼로그가 멈춤 | GIF가 너무 크면 미리보기 디코딩이 event loop을 점유. 권장 크기로 재최적화 |

## 개발 노트

- PySide6 (Qt 6.8+)
- SQLite3 — 마이그레이션은 `_migrate_*` 메서드 체인으로
- 모든 long-lived 매니저는 `parent=qt_app` 스코프 — party rebuild에 영향 없음
- PetWindow는 `Qt.Tool + WindowStaysOnTopHint` (작업표시줄 비노출, 항상 위)
- 다이얼로그는 `parent=None` + `WindowStaysOnTopHint` 권장 (Qt.Tool 부모 z-order 회피)
