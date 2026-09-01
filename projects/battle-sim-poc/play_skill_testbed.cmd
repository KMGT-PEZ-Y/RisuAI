@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"

set "UI_SCRIPT=%~dp0skill_playtest_ui.py"
set "BUNDLED_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if exist "%BUNDLED_PYTHON%" (
    "%BUNDLED_PYTHON%" "%UI_SCRIPT%"
    exit /b %ERRORLEVEL%
)

where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%UI_SCRIPT%"
    exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if not errorlevel 1 (
    python "%UI_SCRIPT%"
    exit /b %ERRORLEVEL%
)

echo Python 3 executable was not found.
exit /b 1

