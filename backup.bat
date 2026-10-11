@echo off
title Questlog backup
cd /d "%~dp0server"
set "PATH=%LOCALAPPDATA%\Microsoft\WinGet\Links;%USERPROFILE%\.local\bin;%PATH%"
rem Keeps the newest 14 backups in %USERPROFILE%\questlog-backups. Safe while the server runs.
uv run python manage.py backup
pause
