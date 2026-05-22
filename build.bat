@echo off
cd /d "%~dp0"
echo Building PokemonBuddy.exe...
".venv\Scripts\python.exe" -m PyInstaller PokemonBuddy.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo BUILD FAILED. Check the messages above.
    exit /b 1
)
echo.
echo OK — dist\PokemonBuddy.exe is ready.
