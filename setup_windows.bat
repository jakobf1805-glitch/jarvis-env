@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python 3 fehlt. Bitte zuerst Python von https://www.python.org/downloads/windows/ installieren.
    exit /b 1
)

py -3 -m venv .venv
if errorlevel 1 exit /b 1
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 exit /b 1
python -m pip install -r requirements-core.txt
if errorlevel 1 exit /b 1
python download_models.py
if errorlevel 1 exit /b 1

echo.
echo Einrichtung fertig. Lege danach deinen OpenRouter-Key nach README.md ab und starte start_windows.bat.
