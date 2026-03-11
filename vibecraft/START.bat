@echo off
title MC Server Manager
color 0A
echo.
echo  ============================================
echo   Minecraft Server Manager v2.0
echo  ============================================
echo.

:: Check Python 3
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found!
    echo.
    echo  Please install Python 3.8+ from:
    echo  https://www.python.org/downloads/
    echo.
    echo  IMPORTANT: Check "Add Python to PATH" during install!
    echo.
    pause
    exit /b 1
)

echo  Python found. Checking dependencies...

:: Install requests silently
python -m pip install requests --quiet 2>nul

echo  Starting MC Server Manager...
echo.

python "%~dp0mc_manager.py"

if errorlevel 1 (
    echo.
    echo  ============================================
    echo   Something went wrong. Error details above.
    echo  ============================================
    pause
)
