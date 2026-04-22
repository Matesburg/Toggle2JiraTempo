@echo off
REM Activates the local virtual environment and runs the Toggle - Jira Tempo sync CLI from the repository root.
setlocal

cd /d "%~dp0"

if not exist "venv\Scripts\activate.bat" (
    echo Virtual environment not found at venv\Scripts\activate.bat
    echo Create the virtual environment first or update start_sync.bat.
    exit /b 1
)

call "venv\Scripts\activate.bat"
python "main.py"

set "exit_code=%ERRORLEVEL%"
endlocal & exit /b %exit_code%