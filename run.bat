@echo off
cd /d "%~dp0backend"
call venv\Scripts\activate.bat
echo Starting Gullak backend at http://127.0.0.1:8000
echo (Keep this window open. Press CTRL+C to stop.)
python manage.py runserver 127.0.0.1:8000
pause
