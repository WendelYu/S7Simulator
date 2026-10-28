@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
  if errorlevel 1 goto :failed
)
.venv\Scripts\python.exe -c "import PySide6, snap7" >nul 2>&1
if errorlevel 1 (
  .venv\Scripts\python.exe -m pip install -e .
  if errorlevel 1 goto :failed
)
.venv\Scripts\python.exe -m s7sim %*
if errorlevel 1 goto :failed
exit /b 0
:failed
echo.
echo Startup failed. Install Python 3.11 or later and check the error above.
pause
exit /b 1
