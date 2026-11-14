@echo off
rem StudEase: one file that checks, sets up and runs everything on Windows.
rem   run.bat          check tools, install, start the database, load data once, start API (8000) and web (5173)
rem   run.bat stop     stop the API, web and database windows and the database
rem   run.bat test     run the backend and frontend tests
rem See SETUP.md for what each step does and for macOS/Linux.
setlocal EnableExtensions
cd /d "%~dp0"
title StudEase launcher

if /i "%~1"=="stop" goto :stop
if /i "%~1"=="test" goto :test

echo.
echo === 1/6  Checking tools ===
set MISSING=0
where python >nul 2>nul || (echo   MISSING: Python 3.12+  ^(https://www.python.org/downloads/^) & set MISSING=1)
where uv     >nul 2>nul || (echo   MISSING: uv            ^(run: pip install uv   or see https://docs.astral.sh/uv/^) & set MISSING=1)
where node   >nul 2>nul || (echo   MISSING: Node.js 20+   ^(https://nodejs.org^) & set MISSING=1)
where npm    >nul 2>nul || (echo   MISSING: npm           ^(comes with Node.js^) & set MISSING=1)
python -c "import sys; sys.path.insert(0,'scripts'); import dev; dev.pg_bin('pg_ctl')" >nul 2>nul || (echo   MISSING: PostgreSQL 14+ ^(https://www.postgresql.org/download/windows/ - or set PGBIN to its bin folder^) & set MISSING=1)
if "%MISSING%"=="1" (
  echo.
  echo Install the missing tools above, open a NEW terminal and run run.bat again.
  pause
  exit /b 1
)
echo   all tools found.

echo.
echo === 2/6  Installing dependencies ^(first run only^) ===
set NEED=0
if not exist backend\.venv set NEED=1
if not exist frontend\node_modules set NEED=1
if "%NEED%"=="1" (
  python scripts\dev.py install
  if errorlevel 1 goto :fail
) else (
  echo   already installed
)
if not exist backend\.env (
  if exist backend\.env.example copy /y backend\.env.example backend\.env >nul
  echo   created backend\.env from the example ^(local defaults are used while its values are empty^)
)

echo.
echo === 3/6  Starting the database ^(PostgreSQL on 127.0.0.1:15433^) ===
python scripts\dev.py db-up
if errorlevel 1 goto :fail

echo.
echo === 4/6  Creating the tables ===
python scripts\dev.py migrate
if errorlevel 1 goto :fail

echo.
echo === 5/6  Loading the synthetic data and the five demo logins ^(first run only^) ===
if not exist .pgdata\loaded.flag (
  python scripts\dev.py load
  if errorlevel 1 goto :fail
  echo loaded> .pgdata\loaded.flag
) else (
  echo   already loaded ^(delete .pgdata\loaded.flag to load again^)
)

echo.
echo === 6/6  Starting the API and the web app ===
call :freeports
start "StudEase API  (http://127.0.0.1:8000)" cmd /k "cd /d %~dp0backend && uv run uvicorn app.main:app --port 8000"
start "StudEase WEB  (http://localhost:5173)" cmd /k "cd /d %~dp0frontend && npm run dev -- --host 127.0.0.1 --port 5173 --strictPort"
echo   waiting for the web app ...
for /l %%i in (1,1,40) do (
  powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5173/ -TimeoutSec 2).StatusCode } catch { exit 1 }" >nul 2>nul && goto :up
  timeout /t 1 >nul
)
echo   the web app is slow to start; open http://localhost:5173 in a minute.
goto :done
:up
start "" http://localhost:5173
:done
echo.
echo ===========================================================================
echo  StudEase is running:   http://localhost:5173      API docs: http://127.0.0.1:8000/api/v1/docs
echo  Demo logins:  learner@example.edu  instructor@example.edu  academic@example.edu
echo                support@example.edu  admin@example.edu
echo  Password:     the DEMO_PASSWORD in backend\.env, or  demo-password-for-local-use  when empty
echo  Stop:         run.bat stop        Tests: run.bat test
echo ===========================================================================
pause
exit /b 0

:test
echo Running backend tests ^(needs the database; starting it first^) ...
python scripts\dev.py db-up || goto :fail
python scripts\dev.py test || goto :fail
pushd frontend & call npx vitest run & popd
exit /b %errorlevel%

:stop
echo Stopping the API and web windows ...
call :freeports
taskkill /f /fi "WINDOWTITLE eq StudEase API*" >nul 2>nul
taskkill /f /fi "WINDOWTITLE eq StudEase WEB*" >nul 2>nul
python scripts\dev.py db-down
echo stopped.
exit /b 0

:fail
echo.
echo *** A step failed ^(see the messages above^). SETUP.md has a troubleshooting table. ***
pause
exit /b 1

:freeports
rem stop anything still listening on the API and web ports (a previous run, or a leftover dev server)
powershell -NoProfile -Command "foreach ($p in 8000,5173,5174) { Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }; Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python|uvicorn|node|uv' -and $_.CommandLine -match 'uvicorn|vite' -and $_.CommandLine -like '*%~dp0*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>nul
exit /b 0
