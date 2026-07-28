@echo off
rem ============================================================
rem  Iron & Ash - one-click launcher for Windows
rem  Double-click this file to play. It finds Python, sets up a
rem  private environment on first run, and starts the game.
rem ============================================================
setlocal EnableExtensions
cd /d "%~dp0"
title Iron ^& Ash

rem -- find a Python 3 interpreter (py launcher first, then python) ----------
set "PYCMD="
where py >nul 2>nul && set "PYCMD=py -3"
if not defined PYCMD (
    where python >nul 2>nul && set "PYCMD=python"
)
if not defined PYCMD (
    echo.
    echo   Python 3 was not found on this PC.
    echo   Install it from https://www.python.org/downloads/
    echo   ^(tick "Add python.exe to PATH" during install^), then run this again.
    echo.
    pause
    exit /b 1
)

rem -- verify the version is 3.11+ -------------------------------------------
%PYCMD% -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 (
    echo.
    echo   Python 3.11 or newer is required. Please update Python from
    echo   https://www.python.org/downloads/ and run this again.
    echo.
    pause
    exit /b 1
)

rem -- first run: create a private venv; optional extras are best-effort -----
if not exist ".venv\Scripts\python.exe" (
    echo First run: preparing the game...
    %PYCMD% -m venv .venv || goto :venvfail
    rem rich and pydantic are optional niceties - the game runs on the standard
    rem library alone, so a failed install must never stop you from playing.
    ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip >nul 2>&1
    ".venv\Scripts\python.exe" -m pip install --quiet rich pydantic >nul 2>&1
)

rem -- play -------------------------------------------------------------------
".venv\Scripts\python.exe" -m iron_and_ash
echo.
pause
exit /b 0

:venvfail
echo.
echo   Setup failed. Check your internet connection and try again.
echo.
pause
exit /b 1
