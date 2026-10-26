@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Run Install-Windows.ps1 first. See README.md.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" scripts\launch.py
pause
