$ErrorActionPreference = "Stop"

# Windows PowerShell 5.1 otherwise emits console text in the OEM codepage even
# under chcp 65001. Keep Turkish text and the launcher artwork clean.
try {
    [Console]::InputEncoding = [System.Text.Encoding]::UTF8
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
    $Host.UI.RawUI.WindowTitle = "EchoWraith - Luna"
} catch { }

$AppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$DataRoot = Join-Path $env:LOCALAPPDATA "EchoWraith"
$RuntimeRoot = Join-Path $DataRoot "runtime"
$LogRoot = Join-Path $DataRoot "logs"
$LauncherLog = Join-Path $LogRoot "launcher.log"
$VenvRoot = Join-Path $RuntimeRoot ".venv"
$Marker = Join-Path $RuntimeRoot "requirements.sha256"
$script:LastPercent = 0

New-Item -ItemType Directory -Force -Path $RuntimeRoot, $LogRoot | Out-Null

function Write-AuroraLine {
    Write-Host "    ~~~~~~~~" -NoNewline -ForegroundColor DarkCyan
    Write-Host "~~~~~~~~~~~~~~~~" -NoNewline -ForegroundColor Cyan
    Write-Host "~~~~~~~~~~~~~~~~" -NoNewline -ForegroundColor Blue
    Write-Host "~~~~~~~~~~~~~~~~" -NoNewline -ForegroundColor Magenta
    Write-Host "~~~~~~~~" -ForegroundColor DarkMagenta
}

function Write-LauncherHeader {
    try { Clear-Host } catch { }
    Write-Host ""
    Write-AuroraLine
    Write-Host ""
    Write-Host "       ______     __          _       __           _ __  __" -ForegroundColor Cyan
    Write-Host "      / ____/____/ /_  ____  | |     / /________ _(_) /_/ /_" -ForegroundColor Cyan
    Write-Host "     / __/ / ___/ __ \/ __ \ | | /| / / ___/ __ `/ / __/ __ \" -ForegroundColor Blue
    Write-Host "    / /___/ /__/ / / / /_/ / | |/ |/ / /  / /_/ / / /_/ / / /" -ForegroundColor Blue
    Write-Host "   /_____/\___/_/ /_/\____/  |__/|__/_/   \__,_/_/\__/_/ /_/" -ForegroundColor Magenta
    Write-Host ""
    Write-Host "        E C H O W R A I T H" -ForegroundColor White
    Write-Host "        Maskot: " -NoNewline -ForegroundColor DarkGray
    Write-Host "Luna" -NoNewline -ForegroundColor Magenta
    Write-Host "       Yapım: " -NoNewline -ForegroundColor DarkGray
    Write-Host "Restless" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "        Ders arşivin hazırlanıyor. Gerekli adımları Luna takip ediyor." -ForegroundColor Gray
    Write-Host ""
    Write-AuroraLine
    Write-Host ""
}

function Write-ProgressBar([int]$Percent) {
    $safe = [Math]::Max(0, [Math]::Min(100, $Percent))
    $width = 46
    $filled = [Math]::Floor($width * $safe / 100)
    $empty = $width - $filled
    Write-Host "        [" -NoNewline -ForegroundColor DarkGray
    if ($filled -gt 0) { Write-Host ("=" * $filled) -NoNewline -ForegroundColor Cyan }
    if ($empty -gt 0) { Write-Host ("-" * $empty) -NoNewline -ForegroundColor DarkGray }
    Write-Host "] " -NoNewline -ForegroundColor DarkGray
    Write-Host ("{0,3}%" -f $safe) -ForegroundColor White
}

function Write-Step([string]$Message, [int]$Percent, [string]$Detail = "") {
    $script:LastPercent = [Math]::Max($script:LastPercent, $Percent)
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$stamp] [$($script:LastPercent)%] $Message"
    if ($Detail) { $line += " - $Detail" }
    Add-Content -Path $LauncherLog -Value $line -Encoding UTF8

    Write-Host "        > " -NoNewline -ForegroundColor Magenta
    Write-Host $Message -ForegroundColor White
    if ($Detail) { Write-Host "          $Detail" -ForegroundColor DarkGray }
    Write-ProgressBar $script:LastPercent
    Write-Host ""
}

function Write-LunaCard([string]$State, [string]$Copy) {
    Write-Host "        +----------------------------------------------------------+" -ForegroundColor DarkBlue
    Write-Host "        |  /\_/\\   " -NoNewline -ForegroundColor Magenta
    Write-Host ("LUNA  {0}" -f $State) -ForegroundColor Magenta
    Write-Host "        | ( o.o )   $Copy" -ForegroundColor Gray
    Write-Host "        |  > ^ <    Ayrıntılı kayıt: $LauncherLog" -ForegroundColor DarkGray
    Write-Host "        +----------------------------------------------------------+" -ForegroundColor DarkBlue
    Write-Host ""
}

function Ensure-AuroraOverhaul {
    $index = Join-Path $AppRoot "web\index.html"
    if (-not (Test-Path $index)) { return }

    $html = [System.IO.File]::ReadAllText($index, [System.Text.Encoding]::UTF8)
    $changed = $false
    if ($html -notmatch "aurora-overhaul\.css") {
        $html = $html.Replace(
            '<link rel="stylesheet" href="./styles.css" />',
            '<link rel="stylesheet" href="./styles.css" />' + [Environment]::NewLine + '    <link rel="stylesheet" href="./aurora-overhaul.css?v=2" />'
        )
        $changed = $true
    }
    if ($html -notmatch "aurora-overhaul\.js") {
        $html = $html.Replace(
            '<script src="./app.js" defer></script>',
            '<script src="./app.js" defer></script>' + [Environment]::NewLine + '    <script src="./aurora-overhaul.js?v=2" defer></script>'
        )
        $changed = $true
    }
    if ($changed) {
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($index, $html, $utf8NoBom)
    }
}

function Invoke-Logged([string]$File, [string[]]$Arguments) {
    & $File @Arguments 2>&1 | Out-File -FilePath $LauncherLog -Append -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { throw "Komut tamamlanamadı: $File" }
}

function Test-Python([string]$Candidate, [string[]]$Prefix = @()) {
    try {
        $version = & $Candidate @Prefix -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($LASTEXITCODE -eq 0 -and [version]$version -ge [version]"3.10" -and [version]$version -lt [version]"3.13") {
            return @{ File = $Candidate; Prefix = $Prefix }
        }
    } catch { }
    return $null
}

try {
    Write-LauncherHeader
    Write-LunaCard "HAZIRLANIYOR" "Sistem ve arayüz bileşenleri kontrol ediliyor."
    Write-Step "EchoWraith başlatılıyor" 6 "Yerel çalışma alanı hazırlanıyor."

    Ensure-AuroraOverhaul
    Write-Step "Aurora arayüzü hazır" 12 "Logo, hareketli arka plan ve Luna görselleri bağlandı."

    $Python = $null
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $Python = Test-Python "py" @("-3.12")
        if (-not $Python) { $Python = Test-Python "py" @("-3.11") }
        if (-not $Python) { $Python = Test-Python "py" @("-3") }
    }
    if (-not $Python -and (Get-Command python -ErrorAction SilentlyContinue)) {
        $Python = Test-Python "python"
    }
    Write-Step "Python çalışma motoru denetlendi" 20

    if (-not $Python) {
        Write-Step "Python otomatik kuruluyor" 26 "Yalnızca kullanıcı hesabına kurulacak."
        $Installer = Join-Path $RuntimeRoot "python-installer.exe"
        $PythonUrl = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
        Invoke-WebRequest -Uri $PythonUrl -OutFile $Installer -UseBasicParsing
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
        Write-Step "İlk kullanım ortamı oluşturuluyor" 34 "Bu adım yalnızca ilk açılışta yapılır."
        & $Python.File @($Python.Prefix) -m venv $VenvRoot
        if ($LASTEXITCODE -ne 0) { throw "Yerel çalışma ortamı oluşturulamadı." }
    }
    Write-Step "Yerel çalışma ortamı hazır" 43

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
    Write-Step "Bileşen sağlığı denetlendi" 52

    if ($CurrentHash -ne $SavedHash -or -not $RuntimeHealthy) {
        if ($SavedHash -and -not $RuntimeHealthy) {
            Write-Step "Eksik bileşenler onarılıyor" 58 "Güvenli otomatik onarım uygulanıyor."
        }
        Write-Step "Gerekli paketler kuruluyor" 64 "İlk açılış birkaç dakika sürebilir; ayrıntılar log dosyasına yazılıyor."
        Invoke-Logged $VenvPython @("-m", "pip", "install", "--upgrade", "pip", "wheel")
        Invoke-Logged $VenvPython @("-m", "pip", "install", "--prefer-binary", "-r", $Requirements)
        Write-Step "Tarayıcı motoru hazırlanıyor" 78
        Invoke-Logged $VenvPython @("-m", "playwright", "install", "chromium")
        Write-Step "Video araçları hazırlanıyor" 88
        Invoke-Logged $VenvPython @("-c", "from static_ffmpeg import run; print(run.get_or_fetch_platform_executables_else_raise())")
        Set-Content -Path $Marker -Value $CurrentHash -Encoding ASCII
    } else {
        Write-Step "Tüm bileşenler güncel" 88 "Yeniden kurulum gerekmiyor."
    }

    Write-Step "Luna paneli açıyor" 96 "Yerel sunucu başlatılıyor."
    $ServerScript = Join-Path $AppRoot "echowraith_server.py"
    Start-Process -FilePath $VenvPythonW -ArgumentList "`"$ServerScript`"" -WorkingDirectory $AppRoot
    Start-Sleep -Milliseconds 900
    Write-Step "EchoWraith hazır" 100 "Panel tarayıcıda açılıyor."
    Write-LunaCard "HAZIR" "Arşiv paneli çalışıyor. Bu pencere kapanabilir."
    Start-Sleep -Milliseconds 650
    exit 0
} catch {
    $message = $_.Exception.Message
    Add-Content -Path $LauncherLog -Value "FATAL: $message`n$($_.ScriptStackTrace)" -Encoding UTF8
    Write-Host ""
    Write-Host "        EchoWraith başlatılamadı" -ForegroundColor Red
    Write-Host "        $message" -ForegroundColor White
    Write-Host "        Ayrıntılı kayıt: $LauncherLog" -ForegroundColor Yellow
    try { Start-Process explorer.exe -ArgumentList "/select,`"$LauncherLog`"" } catch { }
    exit 1
}
