@echo off
title Flezen Bulk Code Extractor
cd /d "%~dp0"
python main.py
if %errorlevel% neq 0 (
    pause
)

