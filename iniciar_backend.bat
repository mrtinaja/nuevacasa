@echo off
echo Cerrando procesos anteriores (si estan corriendo)...
taskkill /F /IM ngrok.exe >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='python3.11.exe'\" | Where-Object { $_.CommandLine -like '*uvicorn*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo.
echo Iniciando backend...
cd /d "%~dp0backend"
start "NuevaCasa - backend" /min .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000

timeout /t 3 /nobreak >nul

echo Iniciando tunel de ngrok (URL fija: https://celtic-lapel-smirk.ngrok-free.dev)...
del ngrok.log >nul 2>&1
start "NuevaCasa - tunel" /min "%LOCALAPPDATA%\Microsoft\WindowsApps\ngrok.exe" http 8000 --url=https://celtic-lapel-smirk.ngrok-free.dev --log ngrok.log

timeout /t 5 /nobreak >nul

echo.
echo ================================================================
echo Listo. Backend + tunel corriendo.
echo URL publica (fija, no cambia mas): https://celtic-lapel-smirk.ngrok-free.dev
echo ================================================================
echo.
echo Esta ventana se cierra sola en unos segundos.
timeout /t 8 /nobreak >nul
