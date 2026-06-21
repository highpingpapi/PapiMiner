@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Stop-PapiMiner.ps1"
if errorlevel 1 pause
