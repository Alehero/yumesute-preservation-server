@echo off
cd /d "%~dp0"
uv run --locked python server.py start
set "result=%errorlevel%"
if not "%result%"=="0" echo Startup failed. Keep the error above; see README troubleshooting.
pause
exit /b %result%
