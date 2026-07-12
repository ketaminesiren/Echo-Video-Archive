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
echo         E C H O W R A I T H   x   L U N A
echo.
echo         Luna sistemi hazirliyor...  ^(^ ^^_^^ ^)
echo         Kod ve tasarim: Luna
echo.
echo         Ilk acilista gerekli bilesenler kurulur; sonraki
echo         acilislar dogrudan paneli baslatir. Lutfen bekle.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0_app\launcher.ps1"
if errorlevel 1 (
  echo.
  echo   Bir sorun olustu. Ayrintilar icin yukaridaki mesajlara bak.
  pause
)
