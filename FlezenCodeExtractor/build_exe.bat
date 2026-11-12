@echo off
title Build Flezen Bulk Code Extractor Executable
cd /d "%~dp0"

echo =======================================================
echo     BUILDING WINDOWS EXECUTABLE VIA PYINSTALLER
echo =======================================================
echo.

python -m PyInstaller ^
    --name="FlezenBulkCodeExtractor" ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --collect-all customtkinter ^
    --hidden-import pymupdf ^
    --hidden-import openpyxl ^
    --hidden-import pytesseract ^
    --hidden-import cv2 ^
    --hidden-import PIL ^
    main.py

if %errorlevel% neq 0 (
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo =======================================================
echo Build complete! Executable is located in dist/FlezenBulkCodeExtractor/
echo =======================================================
pause

