@echo off
REM Opens a SEPARATE Chrome profile that the autopilot can control.
REM First time: log in to LinkedIn and the EasyLeadz (Mr. E) extension in this window.
REM It remembers you after that.

set CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe
if not exist "%CHROME%" set CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe
if not exist "%CHROME%" set CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe
if not exist "%CHROME%" (
  echo Could not find Chrome. Edit this file and set CHROME to the path of chrome.exe
  pause
  exit /b 1
)

start "" "%CHROME%" --remote-debugging-port=9222 --user-data-dir="%USERPROFILE%\easyleadz-chrome" https://www.linkedin.com/feed/
