@echo off
set "APP_DIR=%~dp0"
set "PYTHONW=%APP_DIR%.venv\Scripts\pythonw.exe"

if not exist "%PYTHONW%" (
    echo Missing virtual environment. Run install.bat first.
    pause
    exit /b 1
)

start "" /D "%APP_DIR%" "%PYTHONW%" "%APP_DIR%fastcommandcenter.py"
