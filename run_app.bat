@echo off
echo ===================================================
echo   Starting AI Video Clipper Web Dashboard...
echo ===================================================
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment .venv not found!
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m streamlit run app.py --server.port 8501
pause
