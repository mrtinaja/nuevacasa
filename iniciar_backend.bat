@echo off
echo Cerrando procesos anteriores (si estan corriendo)...
taskkill /F /IM cloudflared.exe >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='python3.11.exe'\" | Where-Object { $_.CommandLine -like '*uvicorn*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo.
echo Iniciando backend...
cd /d "%~dp0backend"
start "NuevaCasa - backend" /min .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000

timeout /t 3 /nobreak >nul

echo Iniciando tunel de Cloudflare...
del cloudflared.log >nul 2>&1
start "NuevaCasa - tunel" cmd /k tools\cloudflared.exe tunnel --url http://localhost:8000 ^> cloudflared.log 2^>^&1

timeout /t 6 /nobreak >nul

echo.
echo ================================================================
findstr /C:"trycloudflare.com" cloudflared.log
echo ================================================================
echo.
echo Esa es la URL nueva del tunel (arriba, entre las lineas ====).
echo Si es distinta a la que ya tenia el sitio, avisale a Claude para
echo que actualice frontend/app.js y resuba a Netlify.
echo.
pause
