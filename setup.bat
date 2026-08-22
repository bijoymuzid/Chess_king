@echo off
title Chess_king Setup
echo ========================================
echo   Chess_king - Automated Setup
echo ========================================
echo.

REM Check if Python is installed
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [OK] Python found:
python --version
echo.

REM Check if venv exists, if not create it
if exist venv\Scripts\python.exe (
    echo [OK] Virtual environment already exists.
) else (
    echo [~] Creating virtual environment...
    python -m venv venv
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
)
echo.

REM Upgrade pip in venv
echo [~] Upgrading pip...
venv\Scripts\python.exe -m pip install --upgrade pip -q
echo [OK] pip upgraded.
echo.

REM Install dependencies
echo [~] Installing required packages (this may take a while)...
venv\Scripts\pip.exe install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo [OK] All dependencies installed successfully.
echo.

REM Check for Stockfish on Desktop
if exist "%USERPROFILE%\Desktop\stockfish\stockfish-windows-x86-64-avx2.exe" (
    echo [OK] Stockfish found at: %USERPROFILE%\Desktop\stockfish\stockfish-windows-x86-64-avx2.exe
) else if exist "%USERPROFILE%\Desktop\stockfish\stockfish-windows-x86-64-modern.exe" (
    echo [OK] Stockfish found at: %USERPROFILE%\Desktop\stockfish\stockfish-windows-x86-64-modern.exe
) else (
    echo [WARNING] Stockfish executable not found on Desktop.
    echo   Download it from: https://stockfishchess.org/download/
    echo   Then place the .exe in: %USERPROFILE%\Desktop\stockfish\
)
echo.

echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo To run Chess_king, double-click: run.bat
echo.
pause