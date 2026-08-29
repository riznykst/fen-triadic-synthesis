@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title FEN - local dev launcher

if /I "%~1"=="stop" (
    echo Stopping the FEN stack...
    docker compose down
    exit /b 0
)

where docker >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker CLI not found. Install Docker Desktop first.
    pause
    exit /b 1
)

echo [1/4] Checking Docker daemon...
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker daemon is not running. Start Docker Desktop and retry.
    pause
    exit /b 1
)

echo [2/4] Building and starting the FEN stack (first build takes a while)...
set FEN_MOCK_VOTING=community
set FEN_MOCK_QUORUM=3
docker compose up --build -d
if errorlevel 1 (
    echo [ERROR] docker compose up failed. See messages above.
    pause
    exit /b 1
)

echo [3/4] Waiting for web services (status-api :8082, mock :8100)...
set /a tries=0
:wait
set /a tries+=1
if !tries! gtr 90 (
    echo [ERROR] services did not become ready in time.
    pause
    exit /b 1
)
powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing http://localhost:8082/healthz -TimeoutSec 2).StatusCode -eq 200 -and (Invoke-WebRequest -UseBasicParsing http://localhost:8100/healthz -TimeoutSec 2).StatusCode -eq 200 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    timeout /t 2 /nobreak >nul
    goto wait
)

echo [4/4] Opening the web interface...
start "" "http://localhost:8082/web/portal/"
start "" "http://localhost:8082/web/widget/demo.html"
echo.
echo FEN stack is running:
echo   Portal : http://localhost:8082/web/portal/
echo   Widget : http://localhost:8082/web/widget/demo.html
echo Stop   : start-dev.bat stop
endlocal