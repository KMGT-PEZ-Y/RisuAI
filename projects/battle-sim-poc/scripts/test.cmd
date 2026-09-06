@echo off
setlocal EnableDelayedExpansion EnableDelayedExpansion
chcp 65001 >nul
set "PYTHONUTF8=1"
set "BUNDLED_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%BUNDLED_PYTHON%" (
    "%BUNDLED_PYTHON%" -m unittest discover -s "%~dp0..\tests" -t "%~dp0.." -p "test_*.py" %*
    exit /b !ERRORLEVEL!
)
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -m unittest discover -s "%~dp0..\tests" -t "%~dp0.." -p "test_*.py" %*
    exit /b !ERRORLEVEL!
)
where python >nul 2>nul
if not errorlevel 1 (
    python -m unittest discover -s "%~dp0..\tests" -t "%~dp0.." -p "test_*.py" %*
    exit /b !ERRORLEVEL!
)
echo Python 3 executable was not found.
exit /b 1
