@echo off
cd /d "%~dp0"
uv run --locked python server.py start
pause
