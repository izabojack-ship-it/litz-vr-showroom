@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 鋁台精機 · VR 線上展間

rem 綁定 0.0.0.0 讓同一區網的手機/平板也能連入
set "HOST=0.0.0.0"
if "%RUN_PORT%"=="" (set "PORT=8990") else (set "PORT=%RUN_PORT%")

rem 取得本機區網 IPv4（供手機連線用）
set "LAN_IP="
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /r /c:"IPv4.*192\.168\." /c:"IPv4.*10\." /c:"IPv4.*172\."') do (
    if not defined LAN_IP set "LAN_IP=%%a"
)
if defined LAN_IP set "LAN_IP=%LAN_IP: =%"
if not defined LAN_IP set "LAN_IP=127.0.0.1"

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

set "VR_URL=http://127.0.0.1:%PORT%/"
set "ADMIN_URL=http://127.0.0.1:%PORT%/admin/"
echo   本機 VR 展間    %VR_URL%
echo   本機 管理後台    %ADMIN_URL%
echo.
echo   手機/平板（同一 Wi-Fi）請開：
echo     VR 展間    http://%LAN_IP%:%PORT%/
echo     管理後台    http://%LAN_IP%:%PORT%/admin/
echo   預設密碼    litz-admin
echo.
echo   ※ 手機連不到時：Windows 防火牆需允許連接埠 %PORT%（見下方指令）
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
