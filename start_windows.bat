@echo off
cd /d "%~dp0"
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:8000"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 server.py
) else (
  python server.py
)
pause
