@echo off
REM Double-click this after you have fetched public markets once in the dashboard.
cd /d "%~dp0.."
call .venv\Scripts\activate.bat
python scripts\live_poll.py
