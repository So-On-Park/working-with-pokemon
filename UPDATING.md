# 업데이트 / 설치 가이드

Pokemon Buddy를 설치하고 업데이트하는 방법이야.

배포 방식이 두 가지야:
- **설치 파일** (`PokemonBuddy-Setup-X.Y.Z.exe`) — 권장. 프로그램 추가/제거에 등록되고 바로가기·자동 업데이트가 편해.
- **압축본** (`PokemonBuddy-...win64.zip`) — 압축만 풀어 바로 실행하는 포터블 방식.

> 💾 **세이브 위치**: 키우던 포켓몬·친밀도·도감·가방·설정은 설치 폴더가 아니라
> `%LOCALAPPDATA%\PokemonBuddy\` 에 저장돼. 그래서 업데이트하거나 프로그램을 제거해도
> 진행도는 그대로 남아.

---

## 1. 처음 설치하기

1. 최신 `PokemonBuddy-Setup-X.Y.Z.exe`를 받아서 실행.
2. 안내를 따라 설치 (관리자 권한 필요 없음 — 사용자 폴더에 설치돼).
3. 끝나면 실행 → 모험자 이름 입력 → 포켓볼 선택 → 첫 버디 등장!

---

## 2. 업데이트하기 (설치본 → 설치본)

이미 설치 파일로 설치한 사람은 제일 간단해.

1. 새 `PokemonBuddy-Setup-X.Y.Z.exe`를 **그냥 실행**.
2. Pokemon Buddy가 켜져 있으면 *"종료할까요?"* 팝업이 떠 → **예** (진행도는 자동 저장돼 있어 안전).
3. 기존 위에 덮어쓰며 업그레이드돼. **구버전을 따로 제거할 필요 없음.**

> 세이브는 설치 폴더 밖에 있으니 업데이트로 사라지지 않아. 스프라이트도 다시 받을 필요 없어.

---

## 3. 압축본 → 설치본으로 옮기기 (1회만)

압축본(zip)으로 쓰던 사람은 데이터 위치가 달라서, 처음 한 번만 옮겨주면 돼.
(이후부터는 위 2번처럼 자동 유지돼.)

### 방법 A — 백업 / 복원 (제일 깔끔, 추천)

구버전 트레이 우클릭 메뉴에 **백업하기**가 있으면:

1. 구버전(압축 푼 폴더) 실행 → 트레이 우클릭 → **백업하기** → `.zip` 저장.
2. 새 `PokemonBuddy-Setup-X.Y.Z.exe` 설치.
3. 새 앱 실행 → 트레이 → **백업 불러오기** → 1번 zip 선택 → 자동 재시작·복원 ✅

→ 포켓몬·친밀도·도감·커스텀 포켓몬·설정까지 전부 그대로 넘어와.

### 방법 B — 파일 직접 복사 (백업 메뉴가 없을 때 / 확실하게)

1. 새 Setup으로 설치하고, **한 번 실행했다가 종료** (그래야 새 데이터 폴더가 생겨).
2. 탐색기 주소창에 `%LOCALAPPDATA%\PokemonBuddy` 입력해서 이동.
3. 옛 압축 폴더에서 복사:
   - **`data\buddy.db`** → `%LOCALAPPDATA%\PokemonBuddy\data\` 에 덮어쓰기
     ← 이 파일 하나면 포켓몬·친밀도·도감·가방·설정이 다 복원돼.
   - (커스텀 포켓몬을 만든 경우만) 옛 `assets\` 폴더의
     `custom_pokemon.json`, `display_scale.json`, `9???_*.gif` →
     `%LOCALAPPDATA%\PokemonBuddy\assets\` 에 복사.
4. 새 앱을 다시 실행 → 복원 완료. (커스텀 관련 파일은 앱이 알아서 제자리로 정리해.)

---

## 4. 백업 / 복원 / 제거

- **백업하기 / 백업 불러오기**: 트레이 메뉴. PC를 옮기거나 큰 변경 전 보관용. zip 한 개로 전체 상태를 담아.
- **제거**: 프로그램 추가/제거에서 제거해도 **세이브 데이터는 남겨둬**. 다시 설치하면 그대로 이어서 플레이할 수 있어.

---

## 5. 개발자용 — 새 버전 배포하기

1. **버전 숫자를 두 군데에서 올리기** (꼭 같게):
   - `pokemon_buddy/__init__.py` 의 `__version__`
   - `installer.iss` 의 `#define MyAppVersion`
2. 프로젝트 폴더에서 **`build_installer.bat` 더블클릭**
   - `build.bat`으로 `dist\PokemonBuddy.exe` 재빌드 → Inno Setup으로 패키징.
   - 결과: `installer_out\PokemonBuddy-Setup-<버전>.exe`
   - 창이 *"계속하려면 아무 키나..."* 에서 멈추니 결과/에러를 확인하고 닫으면 돼.
3. 만들어진 `PokemonBuddy-Setup-<버전>.exe`를 **GitHub Releases**에 올려 배포.

> ⚠️ 주의
> - **버전을 꼭 올려.** 안 올리면 파일명이 겹치고, 프로그램 추가/제거에도 같은 버전으로 보여.
> - **반드시 `build_installer.bat`으로** 빌드해. `installer.iss`만 따로 컴파일하면 옛 `dist\PokemonBuddy.exe`가 그대로 들어갈 수 있어.
> - `build_installer.bat`이 멈추면(`BUILD FAILED`) 대개 **`dist\PokemonBuddy.exe`를 직접 실행 중**이라 그래 → 그 창 닫고 다시.
> - 빌드 도구: 로컬에 `.venv`(PyInstaller 포함)와 [Inno Setup 6](https://jrsoftware.org/isdl.php)가 필요해.
