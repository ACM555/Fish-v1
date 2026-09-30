@echo off
rem ============================================================
rem  Fish-v1 : upload project Python sources to
rem            https://github.com/ACM555/Fish-v1
rem
rem  Usage:
rem      push_python.cmd "what changed this time"
rem      push_python.cmd                 (auto commit message)
rem ============================================================
setlocal
set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS%" set "PS=powershell.exe"
"%PS%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0push_python.ps1" %*
exit /b %ERRORLEVEL%
