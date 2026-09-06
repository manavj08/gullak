@echo off
echo ============================================
echo   Gullak Backend Setup
echo ============================================

cd /d "%~dp0backend"

echo.
echo Checking Python version...
python --version
python -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
    echo.
    echo ERROR: Python 3.11 or newer is required. Please install it from python.org and retry.
    pause
    exit /b 1
)

echo.
echo [1/5] Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Could not create virtual environment. Is Python installed and on PATH?
    pause
    exit /b 1
)

echo.
echo [2/5] Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo [3/5] Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: Dependency installation failed. See the messages above for details.
    pause
    exit /b 1
)

echo.
echo [4/5] Running migrations...
python manage.py migrate
if errorlevel 1 (
    echo.
    echo ERROR: Migrations failed. Check the messages above.
    pause
    exit /b 1
)

echo.
echo [5/5] Loading demo data...
python manage.py seed_demo_data
if errorlevel 1 (
    echo.
    echo WARNING: Demo data load failed or already exists. This is not fatal - continuing.
)

echo.
echo ============================================
echo   Backend setup complete!
echo   Demo login: demo@gullak.app / Demo@12345
echo   Run run.bat to start the server.
echo ============================================
pause
