@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "%~dp0main.py"
) else (
    python "%~dp0main.py"
)
pause
