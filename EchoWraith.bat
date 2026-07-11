@echo off
setlocal
chcp 65001 >nul
title EchoWraith - Luna
color 0B
cls
echo.
echo       ______     __          __      __        _ __  __
echo      / ____/____/ /_  ____  / /___  / /____   (_) /_/ /
echo     / __/ / ___/ __ \/ __ \/ / __ \/ __/ _ \ / / __/ / 
echo    / /___/ /__/ / / / /_/ / / /_/ / /_/  __// / /_/_/  
echo   /_____/\___/_/ /_/\____/_/\____/\__/\___//_/\__(_)   
echo.
echo            Luna sistemi hazırlıyor...  ^(^*^_^^^)
echo            Kod ve tasarım: Luna
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0_app\launcher.ps1"
if errorlevel 1 pause
