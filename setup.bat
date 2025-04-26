@echo off
echo Checking for virtual environment...

if not exist "venv" (
    echo Virtual environment not found. Creating one...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo Failed to create virtual environment. Please ensure Python is installed and in PATH.
        pause
        exit /b %errorlevel%
    )
    echo Virtual environment created.
) else (
    echo Virtual environment found.
)

echo Installing dependencies from requirements.txt...
call venv\Scripts\activate.bat
venv\Scripts\pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Failed to install dependencies.
    pause
    exit /b %errorlevel%
)

echo Setup complete. Dependencies installed.
pause
