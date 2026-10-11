@echo off
setlocal
title Questlog phone access
cd /d "%~dp0server"
set "PATH=%LOCALAPPDATA%\Microsoft\WinGet\Links;%USERPROFILE%\.local\bin;%ProgramFiles%\Tailscale;%PATH%"

where tailscale >nul 2>&1
if errorlevel 1 (
  echo Tailscale isn't installed. Run setup.bat first.
  pause
  exit /b 1
)

echo Before the first run, check two settings in the Tailscale admin console
echo (https://login.tailscale.com/admin/dns): MagicDNS on, HTTPS Certificates enabled.
echo.
tailscale serve --bg 8000
if errorlevel 1 (
  echo.
  echo tailscale serve failed. Make sure you're logged in to Tailscale on this laptop.
  pause
  exit /b 1
)
echo.
tailscale serve status
echo.
choice /m "Create a login token for your phone now"
if errorlevel 2 goto :done
uv run python manage.py add-device "Phone" --kind phone

:done
echo.
echo On the phone: install Tailscale, log in with the same account, open the https address
echo shown above, log in with the phone token, then use "Install app" in the browser menu.
echo run.bat must be running on the laptop for the phone to connect.
pause
