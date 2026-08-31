@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"

set "SIM_SCRIPT=%~dp0run_simulation.py"
set "BUNDLED_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if exist "%BUNDLED_PYTHON%" (
    "%BUNDLED_PYTHON%" "%SIM_SCRIPT%" %*
    exit /b %ERRORLEVEL%
)

where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%SIM_SCRIPT%" %*
    exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if not errorlevel 1 (
    python "%SIM_SCRIPT%" %*
    exit /b %ERRORLEVEL%
)

echo Python 3 executable was not found.
echo Install Python 3 or run this test bed from the Codex workspace runtime.
exit /b 1
