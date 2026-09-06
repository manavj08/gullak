@echo off
echo ============================================
echo   Gullak Frontend Setup
echo ============================================

cd /d "%~dp0frontend"

echo.
echo Installing npm dependencies...
npm install

echo.
echo ============================================
echo   Frontend setup complete!
echo   Run run-frontend.bat to start the dev server.
echo ============================================
pause
