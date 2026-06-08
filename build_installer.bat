@echo off
REM Build the .exe, then wrap it in a Windows installer.
REM Double-click safe: the window stays open (pause) so you can read the
REM result or any error instead of it flashing closed.
cd /d "%~dp0"

echo [1/2] Building PokemonBuddy.exe ...
call "%~dp0build.bat"
if errorlevel 1 (
    echo.
    echo BUILD FAILED — fix the app build before packaging the installer.
    echo ^(Tip: close any running PokemonBuddy.exe first, then retry.^)
    echo.
    pause
    exit /b 1
)

echo.
echo [2/2] Compiling installer with Inno Setup ...

REM Find the Inno Setup compiler (ISCC.exe). Adjust if installed elsewhere.
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
REM Per-user Inno Setup install (no admin) lands under LocalAppData.
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"

if "%ISCC%"=="" (
    echo.
    echo ISCC.exe not found. Install Inno Setup 6 from https://jrsoftware.org/isdl.php
    echo or compile installer.iss manually in the Inno Setup Compiler GUI ^(F9^).
    echo.
    pause
    exit /b 1
)

"%ISCC%" "%~dp0installer.iss"
if errorlevel 1 (
    echo.
    echo INSTALLER BUILD FAILED. Check the messages above.
    echo ^(If it says "Error 32 / file in use", close the old Setup .exe and retry.^)
    echo.
    pause
    exit /b 1
)

echo.
echo OK — the installer is ready in installer_out\ (PokemonBuddy-Setup-VERSION.exe).
echo.
pause
