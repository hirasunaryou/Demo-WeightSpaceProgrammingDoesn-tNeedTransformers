@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
echo ========================================
echo  WSP Live Lab / Windows
echo  Python standard library - no venv
echo ========================================
where py >nul 2>&1
if not errorlevel 1 (
  py -3 launch.py %*
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo Python 3.8+ is required: https://www.python.org/downloads/
    pause
    exit /b 1
  )
  python launch.py %*
)
if errorlevel 1 (
  echo Startup failed. Read the message above.
  pause
  exit /b 1
)
endlocal
exit /b 0
