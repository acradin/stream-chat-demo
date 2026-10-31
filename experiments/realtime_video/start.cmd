@echo off
cd /d "%~dp0..\.."
if not exist ".venv\Scripts\python.exe" (
  echo Project .venv is required. See experiments/realtime_video/README.md.
  pause
  exit /b 1
)
echo Open http://127.0.0.1:8768 in Chrome or Edge.
".venv\Scripts\python.exe" -B -m experiments.realtime_video --provider openai
pause
