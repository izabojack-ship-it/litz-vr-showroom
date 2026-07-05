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

set "VR_URL=http://%HOST%:%PORT%/"
set "ADMIN_URL=http://%HOST%:%PORT%/admin/"
echo   VR 展間    %VR_URL%
echo   管理後台    %ADMIN_URL%
echo   預設密碼    litz-admin
echo.

for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%PORT%" ^| findstr "LISTENING"') do (
    echo   關閉佔用 %PORT% 的舊程序 PID=%%p
    taskkill /F /PID %%p >nul 2>&1
)

python -m pip install -r "server\requirements.txt" -q

timeout /t 1 /nobreak >nul
start "" "%VR_URL%"

python -m uvicorn server.app:app --host %HOST% --port %PORT%
pause
