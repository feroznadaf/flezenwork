@echo off
title Flezen Bulk Code Extractor - Setup & Launch
cd /d "%~dp0"

echo =======================================================
echo          FLEZEN BULK CODE EXTRACTOR
echo =======================================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10+ from python.org and check "Add Python to PATH".
    pause
    exit /b 1
)

echo [1/3] Installing Python dependencies...
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo [2/3] Verifying Playwright browser binaries...
python -m playwright install chromium

echo [3/3] Launching Flezen Bulk Code Extractor...
python main.py

pause

