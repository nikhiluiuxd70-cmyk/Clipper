@echo off
title AI Clipper - Mobile Access Launcher
cd /d "%~dp0"
echo ===================================================
echo     AI Clipper - Running on PC + Mobile Access
echo ===================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found at .venv!
    echo Please run run_app.bat first to set up the environment.
    pause
    exit /b 1
)

echo [1/2] Starting Streamlit server...
start /b "" ".venv\Scripts\python.exe" -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0

timeout /t 3 >nul

echo.
echo ===================================================
echo  MOBILE ACCESS OPTIONS:
echo ===================================================
echo  Option A (Same Wi-Fi network):
echo    Open this on your mobile browser:
echo    http://176.176.176.91:8501
echo.
echo  Option B (Worldwide Public Tunnel for Mobile 4G/5G):
echo    Starting Localtunnel below...
echo ===================================================
echo.

npx localtunnel --port 8501
pause
