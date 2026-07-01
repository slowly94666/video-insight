@echo off
title VideoAgent - Web GUI
cd /d %~dp0
echo Starting VideoAgent Web GUI...
echo Open http://localhost:8080 in your browser
python web_gui.py
if %errorlevel% neq 0 (
    echo.
    echo Failed. Run: pip install -r requirements.txt
    pause
)
