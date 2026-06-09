; Inno Setup script for Pokemon Buddy.
;
; Builds PokemonBuddy-Setup.exe — a proper Windows installer that shows up in
; "프로그램 추가/제거" (Apps & features) with an uninstaller, instead of a
; manually-extracted zip.
;
; Prerequisites:
;   1) Build the app first:  build.bat   (produces dist\PokemonBuddy.exe)
;   2) Install Inno Setup 6: https://jrsoftware.org/isdl.php
;   3) Compile this script:  "ISCC.exe" installer.iss
;        (or open it in the Inno Setup Compiler GUI and press F9)
;      Output lands in:       installer_out\PokemonBuddy-Setup.exe
;
; Data model: the app keeps ALL user state (caught pokemon, friendship,
; custom pokemon, settings) under %LOCALAPPDATA%\PokemonBuddy — NOT inside
; the install folder. So:
;   - It works whether installed per-user or into Program Files (read-only).
;   - Updating (re-running the installer) never touches saved progress.
;   - Uninstalling leaves the save data in place by default; existing users
;     who later reinstall pick up right where they left off.
;
; Existing zip users: on first launch the app auto-imports progress that was
; sitting next to the old .exe (data\ + custom sprites). If they instead
; want to move a save between machines, use the in-app 백업하기 / 백업 불러오기.

#define MyAppName "Pokemon Buddy"
#define MyAppVersion "1.3.0"
#define MyAppPublisher "So-On-Park"
#define MyAppExeName "PokemonBuddy.exe"

[Setup]
; A stable AppId is what ties updates + uninstall together in Add/Remove.
AppId={{8B2C4F1A-7E3D-4C9B-9A12-3F5E7C9B1A20}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
VersionInfoVersion={#MyAppVersion}
DefaultDirName={autopf}\PokemonBuddy
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Per-user install by default → no admin/UAC prompt, lands in
; %LOCALAPPDATA%\Programs\PokemonBuddy and registers a per-user uninstall
; entry. Users with admin rights can still pick a system-wide Program Files
; install at runtime.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
OutputDir=installer_out
OutputBaseFilename=PokemonBuddy-Setup-{#MyAppVersion}
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Tell the shell we register file types (.pokeball / .scroll) so icons refresh.
ChangesAssociations=yes
; We handle a running instance ourselves in [Code] (notify + force close),
; so disable Inno's own Restart Manager prompt to avoid a double dialog.
CloseApplications=no
; The app is windowed (no console) and runs fine on 64-bit Windows.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startup"; Description: "Windows 시작 시 자동 실행 (Run at Windows startup)"; GroupDescription: "추가 옵션:"; Flags: unchecked

[Files]
; The built single-file executable.
Source: "dist\PokemonBuddy.exe"; DestDir: "{app}"; Flags: ignoreversion
; Shipped read-only seed assets (icon + any custom pokemon the distributor
; bundled + a pre-warmed sprite cache if present). The app reads these as a
; fallback; it never writes here. "skipifsourcedoesntexist" keeps the build
; working even if assets\ is trimmed before packaging.
Source: "assets\*"; DestDir: "{app}\assets"; Flags: recursesubdirs ignoreversion skipifsourcedoesntexist
; Shipped library of species-only .pokeball files (import → fresh catch).
Source: "pokeballs\*"; DestDir: "{app}\pokeballs"; Flags: recursesubdirs ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Optional auto-start (per-user Run key) — only added when the user ticks the
; "startup" task; removed cleanly on uninstall.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "PokemonBuddy"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: startup

; ---- File associations (per-user, no admin) ----
; .pokeball — a sent/shared Pokemon. Pokéball icon, double-click → import.
Root: HKCU; Subkey: "Software\Classes\.pokeball"; ValueType: string; ValueData: "PokemonBuddy.pokeball"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\PokemonBuddy.pokeball"; ValueType: string; ValueData: "Pokemon Buddy 포켓몬"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\PokemonBuddy.pokeball\DefaultIcon"; ValueType: string; ValueData: "{app}\assets\pokeball.ico"
Root: HKCU; Subkey: "Software\Classes\PokemonBuddy.pokeball\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

; .scroll — a skill teaching-scroll. Parchment icon, double-click → import.
Root: HKCU; Subkey: "Software\Classes\.scroll"; ValueType: string; ValueData: "PokemonBuddy.scroll"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\PokemonBuddy.scroll"; ValueType: string; ValueData: "Pokemon Buddy 스킬 교본"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\PokemonBuddy.scroll\DefaultIcon"; ValueType: string; ValueData: "{app}\assets\scroll.ico"
Root: HKCU; Subkey: "Software\Classes\PokemonBuddy.scroll\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

[Run]
; Offer to launch right after install.
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

; NOTE: We intentionally do NOT delete %LOCALAPPDATA%\PokemonBuddy on
; uninstall — that's the user's save data. Reinstalling restores their game.

[Code]
{ If Pokemon Buddy is already running, the install can't replace the .exe.
  Detect it, tell the user, and force-close it (safe — all game state is
  committed to the DB continuously, so nothing is lost). }

function IsAppRunning(): Boolean;
var
  ResultCode: Integer;
begin
  Result := False;
  { `find` exits 0 when the process name is present in tasklist, 1 otherwise. }
  if Exec(ExpandConstant('{cmd}'),
          '/C tasklist /FI "IMAGENAME eq ' + '{#MyAppExeName}' + '" | find /I "' + '{#MyAppExeName}' + '"',
          '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    Result := (ResultCode = 0);
end;

procedure ForceCloseApp();
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{cmd}'),
       '/C taskkill /F /IM "' + '{#MyAppExeName}' + '" /T',
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if IsAppRunning() then
  begin
    if MsgBox('Pokemon Buddy가 실행 중입니다.' + #13#10#13#10 +
              '업데이트를 설치하려면 종료해야 합니다. 지금 종료할까요?' + #13#10 +
              '(키우던 포켓몬과 진행 상황은 자동 저장되어 있어 안전합니다.)',
              mbConfirmation, MB_YESNO) = IDYES then
    begin
      ForceCloseApp();
      Sleep(1500);  { let the OS release the file handles before we copy }
    end
    else
      { Non-empty return aborts the install with this message. }
      Result := '업데이트가 취소되었습니다. Pokemon Buddy를 직접 종료한 뒤 다시 설치해 주세요.';
  end;
end;
