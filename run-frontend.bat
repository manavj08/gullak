@echo off
cd /d "%~dp0frontend"
echo Starting Gullak frontend at http://127.0.0.1:5173
echo (Keep this window open. Press CTRL+C to stop.)
npm run dev
pause
