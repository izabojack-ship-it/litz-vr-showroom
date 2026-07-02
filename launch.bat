@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 鋁台精機 · VR 線上展間

set "HOST=127.0.0.1"
if "%RUN_PORT%"=="" (set "PORT=8990") else (set "PORT=%RUN_PORT%")

echo.
echo   ========================================
echo    鋁台精機 - VR 360 環景展間
echo   ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo   [錯誤] 找不到 Python，請先安裝 Python
    pause
    exit /b 1
)

set "URL=http://%HOST%:%PORT%/"
echo   網址  %URL%
echo.

timeout /t 1 /nobreak >nul
start "" "%URL%"
python -m http.server %PORT% --bind %HOST%
pause
