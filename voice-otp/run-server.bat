@echo off
setlocal
cd /d "%~dp0"

set "BACKEND=%~dp0backend"
set "ADMIN=d:\dashbord-admin"
if exist "%~dp0..\dashbord-admin\package.json" set "ADMIN=%~dp0..\dashbord-admin"
if exist "%~dp0..\..\dashbord-admin\package.json" set "ADMIN=%~dp0..\..\dashbord-admin"

echo Lancement VoiceOTP
echo   API   : http://127.0.0.1:5000
echo   Admin : http://localhost:3000
echo.

netstat -ano | findstr /R /C:":5000 .*LISTENING" >nul
if errorlevel 1 (
  start "VoiceOTP - API" cmd /k "cd /d "%BACKEND%" && python serve_prod.py"
) else (
  echo API deja en cours sur le port 5000.
)

netstat -ano | findstr /R /C:":3000 .*LISTENING" >nul
if errorlevel 1 (
  start "VoiceOTP - Admin" cmd /k "cd /d "%ADMIN%" && npm start"
) else (
  echo Admin deja en cours sur le port 3000.
)

timeout /t 2 /nobreak >nul
start "" "http://localhost:3000"

echo.
echo Admin ouvert : http://localhost:3000
echo.
pause
