@echo off
REM JARVIS launcher for Windows. Double-click to run.
title JARVIS

cd /d "%~dp0backend"

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

python -c "import flask" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

if not exist .env (
    copy .env.example .env
    echo.
    echo  ============================================================
    echo   No .env file found, so I created one from the template.
    echo   Open backend\.env and paste your Groq API key, then
    echo   run this file again.
    echo  ============================================================
    echo.
    notepad .env
    pause
    exit /b
)

start "" http://localhost:8000
start "" cmd /c "cd /d %~dp0frontend && python -m http.server 8000"

python app.py
pause
