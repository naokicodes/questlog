@echo off
title Questlog server
cd /d "%~dp0server"
set "PATH=%LOCALAPPDATA%\Microsoft\WinGet\Links;%USERPROFILE%\.local\bin;%PATH%"

if not exist config.toml (
  echo Questlog isn't set up yet. Run setup.bat first.
  pause
  exit /b 1
)

echo Questlog is running at http://localhost:8000
echo Keep this window open. Close it to stop the server.
echo.
start "" cmd /c "timeout /t 3 >nul & start http://localhost:8000"
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
