@echo off
setlocal
chcp 65001 >nul
title EchoWraith - Restless
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0_app\launcher.ps1"
if errorlevel 1 pause
