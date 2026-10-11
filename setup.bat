@echo off
setlocal EnableExtensions
title Questlog setup
cd /d "%~dp0"

echo.
echo  Questlog setup
echo  --------------
echo  Installs only these, and only if they're missing: Git, uv, ActivityWatch, Tailscale.
echo  It never upgrades or changes any other software on this PC.
echo.

where winget >nul 2>&1
if errorlevel 1 (
  echo winget isn't available. Install "App Installer" from the Microsoft Store, then run this again.
  goto :fail
)

call :ensure Git.Git "Git"
call :ensure astral-sh.uv "uv, the Python manager"
call :ensure ActivityWatch.ActivityWatch "ActivityWatch"
call :ensure Tailscale.Tailscale "Tailscale"

rem Let this window use tools that were installed a moment ago.
set "PATH=%LOCALAPPDATA%\Microsoft\WinGet\Links;%USERPROFILE%\.local\bin;%PATH%"

where uv >nul 2>&1
if errorlevel 1 (
  echo.
  echo uv is installed, but this window can't see it yet. Close this window and run setup.bat again.
  goto :fail
)

echo.
echo Installing the server's Python packages. uv downloads Python 3.12 too if it's missing...
pushd server
uv sync
if errorlevel 1 (
  popd
  goto :fail
)

if not exist config.toml (
  copy /y config.example.toml config.toml >nul
  echo Created server\config.toml from the example.
)

uv run python manage.py first-run
if errorlevel 1 (
  popd
  goto :fail
)
popd

echo.
echo  Setup finished. Next:
echo    1. Copy the login token above somewhere safe for a minute.
echo    2. Open ActivityWatch once from the Start menu so it starts tracking.
echo    3. Double-click run.bat to start Questlog, then log in with the token.
echo.
pause
exit /b 0

:ensure
rem No ( ) blocks here: a label containing ")" would break them.
winget list --id %~1 -e --accept-source-agreements >nul 2>&1
if errorlevel 1 goto :ensure_install
echo [ok] %~2 is already installed.
exit /b 0

:ensure_install
echo [..] Installing %~2...
winget install --id %~1 -e --silent --accept-package-agreements --accept-source-agreements
if errorlevel 1 echo [!!] %~2 didn't install. Install it by hand, then run setup.bat again.
exit /b 0

:fail
echo.
echo Setup stopped. Fix the problem described above, then run setup.bat again.
pause
exit /b 1
