@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Launch-PapiMiner.ps1"
if errorlevel 1 (
  echo.
  echo PapiMiner failed to launch. Check local logs, or send the error to Codex.
  pause
)
