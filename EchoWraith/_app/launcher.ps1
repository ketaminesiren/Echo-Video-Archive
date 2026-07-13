$ErrorActionPreference = "Stop"
# Windows PowerShell 5.1 otherwise emits console text in the OEM codepage even
# under `chcp 65001`, which turns "..." and Turkish letters into mojibake
# (e.g. "baslatiliyorâ€¦"). Pin the console to UTF-8 so output stays clean.
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
} catch { }
$AppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$DataRoot = Join-Path $env:LOCALAPPDATA "EchoWraith"
$RuntimeRoot = Join-Path $DataRoot "runtime"
$LogRoot = Join-Path $DataRoot "logs"
$LauncherLog = Join-Path $LogRoot "launcher.log"
$VenvRoot = Join-Path $RuntimeRoot ".venv"
$Marker = Join-Path $RuntimeRoot "requirements.sha256"

# A .bat file cannot carry its own Explorer icon. Apply Luna's bundled icon to
# the console window instead; failures are intentionally ignored on terminals
# that do not expose a classic console window.
$script:LunaConsoleIcon = $null
try {
    $IconPath = Join-Path $AppRoot "web\assets\luna-launcher-icon.ico"
    if (Test-Path $IconPath) {
        Add-Type -AssemblyName System.Drawing
        Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class EchoWraithConsoleIcon {
    [DllImport("kernel32.dll")]
    public static extern IntPtr GetConsoleWindow();

    [DllImport("user32.dll", CharSet = CharSet.Auto)]
    public static extern IntPtr SendMessage(IntPtr hWnd, uint message, IntPtr wParam, IntPtr lParam);
}
"@
        $window = [EchoWraithConsoleIcon]::GetConsoleWindow()
        if ($window -ne [IntPtr]::Zero) {
            $script:LunaConsoleIcon = New-Object System.Drawing.Icon($IconPath)
            [void][EchoWraithConsoleIcon]::SendMessage($window, 0x0080, [IntPtr]::Zero, $script:LunaConsoleIcon.Handle)
            [void][EchoWraithConsoleIcon]::SendMessage($window, 0x0080, [IntPtr]1, $script:LunaConsoleIcon.Handle)
        }
    }
} catch { }

New-Item -ItemType Directory -Force -Path $RuntimeRoot, $LogRoot | Out-Null

function Write-Step([string]$Message) {
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$stamp] $Message"
    Write-Host "`n  $Message" -ForegroundColor Cyan
    Add-Content -Path $LauncherLog -Value $line -Encoding UTF8
}

function Write-LunaBanner {
    $art = @(
        '        /\_/\\',
        '       ( o.o )    LUNA',
        '        > ^ <     EchoWraith kurulum sihirbazı',
        '',
        '  Ders arşivini hazırlıyorum; gereken bileşenleri ben yöneteceğim.'
    )
    Write-Host ''
    foreach ($line in $art) { Write-Host "  $line" -ForegroundColor Magenta }
    Write-Host ''
}

function Invoke-Logged([string]$File, [string[]]$Arguments) {
    # Keep the pip/playwright/ffmpeg firehose out of the console; only the clean
    # Write-Step messages should be visible. Everything still goes to the log.
    & $File @Arguments 2>&1 | Out-File -FilePath $LauncherLog -Append -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { throw "Komut tamamlanamadı: $File" }
}

# The one-time component install needs the internet, and a momentary DNS/Wi-Fi
# blip used to kill the whole launch with a scary pip traceback. Retry each
# network step a few times with a growing pause so a transient hiccup recovers
# on its own instead of failing the first-run setup.
function Invoke-WithRetry([scriptblock]$Action, [string]$What, [int]$Max = 4) {
    for ($attempt = 1; $attempt -le $Max; $attempt++) {
        try { & $Action; return }
        catch {
            Add-Content -Path $LauncherLog -Value "RETRY ${What} ${attempt}/${Max}: $($_.Exception.Message)" -Encoding UTF8
            if ($attempt -ge $Max) { throw }
            Write-Step "$What tamamlanamadı ($attempt/$Max); internet bağlantısı beklenip yeniden denenecek..."
            Start-Sleep -Seconds ([Math]::Min(30, 6 * $attempt))
        }
    }
}

# Wait until a real DNS lookup for the package servers succeeds. On networks
# that are simply slow to come up this gives them time; if the machine truly
# has no route out we fall through and the retry/telling error handles it.
function Wait-ForNetwork([int]$Max = 8) {
    for ($attempt = 1; $attempt -le $Max; $attempt++) {
        foreach ($server in @("pypi.org", "files.pythonhosted.org")) {
            try {
                if ([System.Net.Dns]::GetHostAddresses($server)) { return $true }
            } catch {}
        }
        Write-Step "İnternet bağlantısı bekleniyor ($attempt/$Max)... Wi-Fi veya kabloya bağlı olduğundan emin ol."
        Start-Sleep -Seconds 5
    }
    return $false
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
    Write-LunaBanner
    Write-Step "EchoWraith başlatılıyor..."
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
        Write-Step "Gerekli Python bileşeni bulunamadı; kullanıcı hesabına otomatik kuruluyor..."
        $Installer = Join-Path $RuntimeRoot "python-installer.exe"
        $PythonUrl = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
        Wait-ForNetwork | Out-Null
        Invoke-WithRetry { Invoke-WebRequest -Uri $PythonUrl -OutFile $Installer -UseBasicParsing } "Python indirme"
        $process = Start-Process -FilePath $Installer -ArgumentList "/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_test=0", "Include_launcher=1" -Wait -PassThru
        if ($process.ExitCode -ne 0) { throw "Python otomatik kurulamadı (kod $($process.ExitCode))." }
        Remove-Item $Installer -Force -ErrorAction SilentlyContinue
        $installed = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
        if (-not (Test-Path $installed)) { throw "Python kuruldu ancak çalıştırma dosyası bulunamadı." }
        $Python = @{ File = $installed; Prefix = @() }
    }

    $VenvPython = Join-Path $VenvRoot "Scripts\python.exe"
    $VenvPythonW = Join-Path $VenvRoot "Scripts\pythonw.exe"
    if (-not (Test-Path $VenvPython)) {
        Write-Step "İlk kullanım ortamı hazırlanıyor (yalnızca bir kez)..."
        & $Python.File @($Python.Prefix) -m venv $VenvRoot
        if ($LASTEXITCODE -ne 0) { throw "Yerel çalışma ortamı oluşturulamadı." }
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
            Write-Step "Çalışma bileşenlerinden biri eksik; otomatik onarım uygulanıyor..."
        }
        Write-Step "Gerekli bileşenler kuruluyor; ilk açılış birkaç dakika sürebilir..."
        Wait-ForNetwork | Out-Null
        $pipRetry = @("--retries", "6", "--timeout", "40")
        Invoke-WithRetry { Invoke-Logged $VenvPython (@("-m", "pip", "install", "--upgrade") + $pipRetry + @("pip", "wheel")) } "Kurulum araçları"
        Invoke-WithRetry { Invoke-Logged $VenvPython (@("-m", "pip", "install", "--prefer-binary") + $pipRetry + @("-r", $Requirements)) } "Gerekli bileşenler"
        Write-Step "Görünmeyen tarayıcı motoru hazırlanıyor..."
        Invoke-WithRetry { Invoke-Logged $VenvPython @("-m", "playwright", "install", "chromium") } "Tarayıcı motoru"
        Write-Step "Video araçları hazırlanıyor..."
        Invoke-WithRetry { Invoke-Logged $VenvPython @("-c", "from static_ffmpeg import run; print(run.get_or_fetch_platform_executables_else_raise())") } "Video araçları"
        Set-Content -Path $Marker -Value $CurrentHash -Encoding ASCII
    }

    Write-Step "Hazır. Luna paneli tarayıcıda açıyor..."
    $ServerScript = Join-Path $AppRoot "echowraith_server.py"
    Start-Process -FilePath $VenvPythonW -ArgumentList "`"$ServerScript`"" -WorkingDirectory $AppRoot
    Start-Sleep -Milliseconds 900
    exit 0
} catch {
    $message = $_.Exception.Message
    Add-Content -Path $LauncherLog -Value "FATAL: $message`n$($_.ScriptStackTrace)" -Encoding UTF8
    $networkHit = $message -match "getaddrinfo|NewConnectionError|Failed to establish|ConnectionError|actively refused|timed out|11001|11004|Ad çözümleme|çözümlenemedi|uzak ad"
    if ($networkHit) {
        Write-Host "`n  EchoWraith ilk kurulum için internete bağlanamadı." -ForegroundColor Red
        Write-Host "  Yapman gereken: internet bağlantını kontrol et (Wi-Fi/kablo), sonra" -ForegroundColor Yellow
        Write-Host "  BAŞLAT dosyasına yeniden çift tıkla. Kaldığı yerden kurulumu sürdürür." -ForegroundColor Yellow
        Write-Host "  Not: Okul/iş ağı python.org veya pypi.org adreslerini engelliyorsa," -ForegroundColor DarkYellow
        Write-Host "  başka bir ağda (ör. telefon hotspot) ilk kurulumu bir kez tamamlaman yeter." -ForegroundColor DarkYellow
    } else {
        Write-Host "`n  EchoWraith başlatılamadı: $message" -ForegroundColor Red
    }
    Write-Host "  Ayrıntılı kayıt: $LauncherLog" -ForegroundColor Yellow
    try { Start-Process explorer.exe -ArgumentList "/select,`"$LauncherLog`"" } catch {}
    exit 1
}
