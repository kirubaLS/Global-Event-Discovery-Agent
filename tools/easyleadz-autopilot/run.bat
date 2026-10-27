@echo off
REM ================== SETTINGS - edit these, then save ==================

REM Google Sheet web app URL (ends in /exec) and the TOKEN you put in sheet-webapp.gs.
REM Leave both empty to work with CSV files only.
set SHEET_URL=
set TOKEN=

REM CSV file with LinkedIn URLs. Leave empty to read the leads from the Google Sheet instead.
set CSV_FILE=leads.csv

REM Stop after this many phone numbers (your EasyLeadz daily cap is 170).
set MAX=170

REM Profiles per minute. Lower is safer for your LinkedIn account.
set PER_MINUTE=3

REM =======================================================================

cd /d "%~dp0"

where node >nul 2>nul
if errorlevel 1 (
  echo Node.js is not installed. Get the LTS version from https://nodejs.org and run this again.
  pause
  exit /b 1
)
node -e "process.exit(+process.versions.node.split('.')[0] < 22 ? 1 : 0)"
if errorlevel 1 (
  echo Your Node.js is too old. Install version 22 or newer from https://nodejs.org
  pause
  exit /b 1
)

set ARGS=--max %MAX% --per-minute %PER_MINUTE%
if not "%SHEET_URL%"=="" set ARGS=%ARGS% --sheet "%SHEET_URL%" --token "%TOKEN%"

if "%CSV_FILE%"=="" (
  node autopilot.mjs %ARGS%
) else (
  node autopilot.mjs "%CSV_FILE%" %ARGS%
)
echo.
pause
