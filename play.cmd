@echo off
REM Launch The Valley. Double-click this file.
REM
REM pythonw.exe, not python.exe: no console window, GUI still appears.
REM
REM Do NOT add start /min or PowerShell's -WindowStyle Hidden here. On
REM Windows that show-state rides along to the FIRST window the process
REM creates, which is the pywebview window itself and not the console, so
REM the game launches completely invisibly.
REM
REM No output redirect either: with start, redirection applies to start
REM itself and silently yields an empty file. main.py opens its own log at
REM %LOCALAPPDATA%\TheValley\launch.log instead.
REM
REM This file must keep CRLF line endings. cmd.exe mis-parses LF-only
REM batch files: every REM line above becomes a bad command.

setlocal
cd /d "%~dp0"

where pythonw >nul 2>nul
if errorlevel 1 (
  echo pythonw.exe is not on PATH. Install Python 3.11+, or run: python main.py
  pause
  exit /b 1
)

start "" pythonw -u main.py
echo The Valley is starting.
echo If no window appears, read %LOCALAPPDATA%\TheValley\launch.log
endlocal
