@echo off
title Chess_king
echo ========================================
echo   Chess_king Chess Bot
echo ========================================
echo.

REM Check if virtual environment exists
if not exist venv\Scripts\python.exe (
    echo [ERROR] Virtual environment not found.
    echo Please run setup.bat first by double-clicking it.
    echo.
    pause
    exit /b 1
)

echo [OK] Launching Chess_king...
venv\Scripts\python.exe src\gui.py
pause