@echo off
echo ========================================
echo   VideoAgent Setup
echo ========================================
echo.

echo [1/3] Installing Python dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo [2/3] Downloading yt-dlp and ffmpeg...
python install.py
if %errorlevel% neq 0 (
    echo Failed to download tools
    pause
    exit /b 1
)

echo.
echo [3/3] Checking .env config...
if not exist ".env" (
    copy .env.example .env
    echo.
    echo *** IMPORTANT ***
    echo Please edit .env and set your MIMO_API_KEY
    echo Then run: python gui.py
    notepad .env
) else (
    echo .env already exists, skipping
)

echo.
echo ========================================
echo   Setup complete! Run: python gui.py
echo ========================================
pause
