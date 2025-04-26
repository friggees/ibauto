@echo off
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Starting Flask Dashboard Server...
python app/main.py
pause
