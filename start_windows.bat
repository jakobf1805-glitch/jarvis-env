@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Die Einrichtung wird jetzt einmalig ausgefuehrt …
    call setup_windows.bat
    if errorlevel 1 exit /b 1
)

call .venv\Scripts\activate.bat
python jarvis_dashboard.py --open-browser
