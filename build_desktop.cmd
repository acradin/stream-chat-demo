@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "apps\desktop\window\packaging\build.ps1" %*
if errorlevel 1 (
  echo Build failed. See INSTALLER.md.
  pause
  exit /b 1
)
echo Installer is in dist.
pause
