$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$DataRoot = Join-Path $env:LOCALAPPDATA "EchoWraith"
$RuntimeRoot = Join-Path $DataRoot "runtime"
$LogRoot = Join-Path $DataRoot "logs"
$LauncherLog = Join-Path $LogRoot "launcher.log"
$VenvRoot = Join-Path $RuntimeRoot ".venv"
$Marker = Join-Path $RuntimeRoot "requirements.sha256"

New-Item -ItemType Directory -Force -Path $RuntimeRoot, $LogRoot | Out-Null

function Write-Step([string]$Message) {
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$stamp] $Message"
    Write-Host "`n  $Message" -ForegroundColor Cyan
    Add-Content -Path $LauncherLog -Value $line -Encoding UTF8
}

function Invoke-Logged([string]$File, [string[]]$Arguments) {
    & $File @Arguments 2>&1 | Tee-Object -FilePath $LauncherLog -Append
    if ($LASTEXITCODE -ne 0) { throw "Komut tamamlanamadi: $File" }
}

function Test-Python([string]$Candidate, [string[]]$Prefix = @()) {
    try {
        $version = & $Candidate @Prefix -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($LASTEXITCODE -eq 0 -and [version]$version -ge [version]"3.10" -and [version]$version -lt [version]"3.13") {
            return @{ File = $Candidate; Prefix = $Prefix }
        }
    } catch {}
    return $null
}

try {
    Write-Step "EchoWraith baslatiliyor…"
    $Python = $null
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $Python = Test-Python "py" @("-3.12")
        if (-not $Python) { $Python = Test-Python "py" @("-3.11") }
        if (-not $Python) { $Python = Test-Python "py" @("-3") }
    }
    if (-not $Python -and (Get-Command python -ErrorAction SilentlyContinue)) {
        $Python = Test-Python "python"
    }

    if (-not $Python) {
        Write-Step "Gerekli Python bileseni bulunamadi; kullanici hesabina otomatik kuruluyor…"
        $Installer = Join-Path $RuntimeRoot "python-installer.exe"
        $PythonUrl = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
        Invoke-WebRequest -Uri $PythonUrl -OutFile $Installer -UseBasicParsing
        $process = Start-Process -FilePath $Installer -ArgumentList "/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_test=0", "Include_launcher=1" -Wait -PassThru
        if ($process.ExitCode -ne 0) { throw "Python otomatik kurulamadi (kod $($process.ExitCode))." }
        Remove-Item $Installer -Force -ErrorAction SilentlyContinue
        $installed = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
        if (-not (Test-Path $installed)) { throw "Python kuruldu ancak calistirma dosyasi bulunamadi." }
        $Python = @{ File = $installed; Prefix = @() }
    }

    $VenvPython = Join-Path $VenvRoot "Scripts\python.exe"
    $VenvPythonW = Join-Path $VenvRoot "Scripts\pythonw.exe"
    if (-not (Test-Path $VenvPython)) {
        Write-Step "İlk kullanim ortami hazirlaniyor (yalnizca bir kez)…"
        & $Python.File @($Python.Prefix) -m venv $VenvRoot
        if ($LASTEXITCODE -ne 0) { throw "Yerel calisma ortami olusturulamadi." }
    }

    $Requirements = Join-Path $AppRoot "requirements.txt"
    $CurrentHash = (Get-FileHash -Algorithm SHA256 $Requirements).Hash
    $SavedHash = if (Test-Path $Marker) { (Get-Content $Marker -Raw).Trim() } else { "" }
    $RuntimeHealthy = $false
    if (Test-Path $VenvPython) {
        try {
            & $VenvPython -c "from pathlib import Path; import requests, bbb_dl, static_ffmpeg, yt_dlp, faster_whisper; from playwright.sync_api import sync_playwright; p=sync_playwright().start(); e=Path(p.chromium.executable_path); p.stop(); raise SystemExit(0 if e.exists() else 1)" 2>> $LauncherLog
            $RuntimeHealthy = ($LASTEXITCODE -eq 0)
        } catch { $RuntimeHealthy = $false }
    }
    if ($CurrentHash -ne $SavedHash -or -not $RuntimeHealthy) {
        if ($SavedHash -and -not $RuntimeHealthy) {
            Write-Step "calisma bilesenlerinden biri eksik; otomatik onarim uygulaniyor…"
        }
        Write-Step "Gerekli bilesenler kuruluyor; ilk acilis birkac dakika surebilir…"
        Invoke-Logged $VenvPython @("-m", "pip", "install", "--upgrade", "pip", "wheel")
        Invoke-Logged $VenvPython @("-m", "pip", "install", "--prefer-binary", "-r", $Requirements)
        Write-Step "Gorunmeyen tarayici motoru hazirlaniyor…"
        Invoke-Logged $VenvPython @("-m", "playwright", "install", "chromium")
        Write-Step "Video araclari hazirlaniyor…"
        Invoke-Logged $VenvPython @("-c", "from static_ffmpeg import run; print(run.get_or_fetch_platform_executables_else_raise())")
        Set-Content -Path $Marker -Value $CurrentHash -Encoding ASCII
    }

    Write-Step "Hazir. EchoWraith tarayicida aciliyor…"
    $ServerScript = Join-Path $AppRoot "echowraith_server.py"
    Start-Process -FilePath $VenvPythonW -ArgumentList "`"$ServerScript`"" -WorkingDirectory $AppRoot
    Start-Sleep -Milliseconds 900
    exit 0
} catch {
    $message = $_.Exception.Message
    Add-Content -Path $LauncherLog -Value "FATAL: $message`n$($_.ScriptStackTrace)" -Encoding UTF8
    Write-Host "`n  EchoWraith baslatilamadi: $message" -ForegroundColor Red
    Write-Host "  Ayrintili kayit: $LauncherLog" -ForegroundColor Yellow
    try { Start-Process explorer.exe -ArgumentList "/select,`"$LauncherLog`"" } catch {}
    exit 1
}
