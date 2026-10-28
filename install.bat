@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 goto :error
)

echo Installing dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo Done. Run run.bat to start PAMF Replacer.
pause
exit /b 0

:error
echo.
echo Installation failed.
pause
exit /b 1
