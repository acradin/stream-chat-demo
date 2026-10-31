@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -B -m deploy.aws.deploy package
) else (
  py -3 -B -m deploy.aws.deploy package
)
if errorlevel 1 exit /b %errorlevel%
echo AWS package prepared. See AWS.md for the deployment steps.
