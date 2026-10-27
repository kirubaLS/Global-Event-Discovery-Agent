@echo off
REM Opens a separate Chrome profile that the autopilot script can control.
REM Log in to LinkedIn and the EasyLeadz (Mr. E) extension in this window once; it remembers you.
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%USERPROFILE%\easyleadz-chrome" https://www.linkedin.com/feed/
