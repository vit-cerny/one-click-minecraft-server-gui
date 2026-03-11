@echo off
setlocal enabledelayedexpansion
title MC Server Manager - Setup & Launcher
color 0A

echo.
echo  ============================================================
echo    Minecraft Server Manager v2.0  -  Auto Setup ^& Launch
echo  ============================================================
echo.

set "DIR=%~dp0"
set "PY=%DIR%python-3_8_0.exe"
set "PLAYIT_MSI=%DIR%playit-windows-x86_64-signed.msi"
set "APP=%DIR%mc_manager.py"

:: ══════════════════════════════════════════════
::  STEP 1 — PYTHON
:: ══════════════════════════════════════════════
echo  [1/3] Checking Python...

python --version >nul 2>&1
if %errorlevel% == 0 (
    echo        Python already installed. Skipping.
    goto :check_requests
)

if exist "%PY%" (
    echo        Installing Python 3.8 from bundled installer...
    echo        Please wait ~30 seconds...
    echo.
    "%PY%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=1
    if !errorlevel! neq 0 (
        echo  [ERROR] Python install failed. Run python-3_8_0.exe manually.
        pause & exit /b 1
    )
    echo        Python installed!
    call :refresh_path
) else (
    echo        python-3_8_0.exe not found. Downloading from python.org...
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.8.0/python-3.8.0-amd64.exe' -OutFile '%PY%' -UseBasicParsing"
    if not exist "%PY%" (
        echo  [ERROR] Download failed. Install Python manually: https://www.python.org
        pause & exit /b 1
    )
    "%PY%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=1
    call :refresh_path
    echo        Python installed!
)

:check_requests
:: ══════════════════════════════════════════════
::  STEP 2 — PYTHON PACKAGES
:: ══════════════════════════════════════════════
echo.
echo  [2/3] Installing Python packages (requests)...
python -m pip install requests --quiet --upgrade 2>nul
if %errorlevel% == 0 (
    echo        OK.
) else (
    echo        Warning: requests install failed. Downloads may be slower.
)

:: ══════════════════════════════════════════════
::  STEP 3 — PLAYIT.GG
:: ══════════════════════════════════════════════
echo.
echo  [3/3] Checking playit.gg...

if exist "%DIR%playit.exe" (
    echo        playit.exe already in folder. Skipping.
    echo %DIR%playit.exe> "%DIR%.playit_path"
    goto :launch
)

if exist "%PLAYIT_MSI%" (
    echo        Installing playit.gg from bundled MSI...
    msiexec /i "%PLAYIT_MSI%" /quiet /norestart
    if !errorlevel! == 0 (
        echo        playit.gg installed!
        for %%P in (
            "%ProgramFiles%\playit\playit.exe"
            "%ProgramFiles(x86)%\playit\playit.exe"
            "%LOCALAPPDATA%\playit\playit.exe"
            "%LOCALAPPDATA%\Programs\playit\playit.exe"
        ) do (
            if exist "%%~P" (
                copy /Y "%%~P" "%DIR%playit.exe" >nul 2>&1
                echo %%~P> "%DIR%.playit_path"
            )
        )
    ) else (
        echo        Warning: MSI install had an error. Try running the MSI manually.
    )
) else (
    echo        Downloading playit.exe from github...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/playit-cloud/playit-agent/releases/latest/download/playit-windows-x86_64-signed.exe' -OutFile '%DIR%playit.exe' -UseBasicParsing" 2>nul
    if exist "%DIR%playit.exe" (
        echo        playit.exe downloaded!
        echo %DIR%playit.exe> "%DIR%.playit_path"
    ) else (
        echo        Warning: Could not download playit. Use the playit.gg tab in the app.
    )
)

:: ══════════════════════════════════════════════
::  LAUNCH
:: ══════════════════════════════════════════════
:launch
echo.
echo  ============================================================
echo    All done! Launching Minecraft Server Manager...
echo  ============================================================
echo.

if not exist "%APP%" (
    echo  [ERROR] mc_manager.py not found in this folder!
    pause & exit /b 1
)

python "%APP%"

if %errorlevel% neq 0 (
    echo.
    echo  ============================================================
    echo   App exited with an error. See details above.
    echo  ============================================================
    pause
)
goto :eof

:refresh_path
for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "USER_PATH=%%B"
for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH 2^>nul') do set "SYS_PATH=%%B"
set "PATH=%SYS_PATH%;%USER_PATH%"
goto :eof
