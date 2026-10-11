@echo off
title Questlog server
cd /d "%~dp0server"
set "PATH=%LOCALAPPDATA%\Microsoft\WinGet\Links;%USERPROFILE%\.local\bin;%PATH%"

if not exist config.toml goto :no_setup

rem Start ActivityWatch if it isn't running yet. No ( ) blocks: paths can contain ")".
tasklist /fi "imagename eq aw-qt.exe" | find /i "aw-qt.exe" >nul
if not errorlevel 1 goto :aw_ready
set "AW=%LOCALAPPDATA%\Programs\ActivityWatch\aw-qt.exe"
if not exist "%AW%" set "AW=%ProgramFiles%\ActivityWatch\aw-qt.exe"
if exist "%AW%" goto :aw_start
echo ActivityWatch isn't installed, so auto quests can't be checked.
echo Install it with: winget install --id ActivityWatch.ActivityWatch -e
echo.
goto :aw_ready

:aw_start
echo Starting ActivityWatch...
start "" "%AW%"

:aw_ready
echo Questlog is running at http://localhost:8000
echo Keep this window open. Close it to stop the server.
echo.
start "" cmd /c "timeout /t 3 >nul & start http://localhost:8000"
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
exit /b 0

:no_setup
echo Questlog isn't set up yet. Run setup.bat first.
pause
exit /b 1
