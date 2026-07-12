@echo off
setlocal
chcp 65001 >nul
title EchoWraith - Luna
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0_app\launcher.ps1"
exit /b %errorlevel%
