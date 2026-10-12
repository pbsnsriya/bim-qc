@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 -c "import ifcopenshell" >nul 2>nul
  if errorlevel 1 py -3 -m pip install "ifcopenshell>=0.8.5,<0.9"
) else (
  python -c "import ifcopenshell" >nul 2>nul
  if errorlevel 1 python -m pip install "ifcopenshell>=0.8.5,<0.9"
)
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:8000"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 server.py
) else (
  python server.py
)
pause
