@echo off
title VideoAgent
cd /d %~dp0
python gui.py
if %errorlevel% neq 0 (
    echo.
    echo Failed. Run setup.bat first.
    pause
)
