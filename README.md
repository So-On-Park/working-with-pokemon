# Pokemon Buddy

Windows 데스크탑 위에서 함께 지내는 포켓몬 버디 앱입니다.

> 안정 배포와 실제 개발은 `develop` 브랜치에서 진행합니다.  
> `main` 브랜치는 프로젝트 안내와 진입점 역할만 합니다.

## 바로가기

- 개발 브랜치: [`develop`](https://github.com/So-On-Park/working-with-pokemon/tree/develop)
- 릴리스: [`Releases`](https://github.com/So-On-Park/working-with-pokemon/releases)
- 최신 Windows 배포 파일: Releases에서 `PokemonBuddy-v0.1.1-win64.zip` 다운로드

## 앱 개요

Pokemon Buddy는 PySide6 기반 Windows 데스크탑 펫 앱입니다.

주요 기능:

- 첫 실행 시 모험자 이름 입력 + 포켓볼 선택으로 시작
- 데스크탑 위 포켓몬 파티 최대 3마리
- 친밀도, 경험치, 진화, 아이템, 야생 인카운터
- 내 포켓몬 가방, 도감, 인벤토리, 리마인더
- 사용자가 직접 만든 GIF로 커스텀 포켓몬 추가
- 백업 / 복원으로 현재 포켓몬 상태 이전
- Windows용 단일 실행 파일 배포

## 개발

개발 작업은 `develop` 브랜치에서 진행합니다.

```cmd
git checkout develop
.venv\Scripts\python.exe -m pytest tests/
build.bat
```

## 배포

릴리스 zip은 `develop` 브랜치 기준으로 빌드합니다.

```cmd
build.bat
```

생성물:

- `dist/PokemonBuddy.exe`
- `PokemonBuddy-v0.1.1-win64.zip`

## 브랜치 정책

- `main`: 프로젝트 소개 / 안정 진입점
- `develop`: 실제 코드 개발 / 빌드 / 릴리스 기준
