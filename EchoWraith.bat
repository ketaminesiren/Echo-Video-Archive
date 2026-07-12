@echo off
setlocal
chcp 65001 >nul
title EchoWraith - Luna
color 0B
mode con cols=118 lines=38 >nul 2>&1
cls
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0_app\launcher.ps1"
if errorlevel 1 (
  echo.
  echo   EchoWraith baslatilamadi. Ayrintili hata kaydi otomatik acildi.
  pause
)
