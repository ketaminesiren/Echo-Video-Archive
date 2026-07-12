$ErrorActionPreference = "Stop"

try {
    [Console]::InputEncoding = [System.Text.Encoding]::UTF8
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
$StatusPath = Join-Path $RuntimeRoot "launcher-status.json"
$StatusTemp = Join-Path $RuntimeRoot "launcher-status.tmp"
$CancelPath = Join-Path $RuntimeRoot "launcher-cancel.flag"
$LauncherWindow = Join-Path $AppRoot "launcher_window.ps1"
$script:LauncherLines = New-Object System.Collections.Generic.List[string]
$script:LastPercent = 0
$script:WindowProcess = $null
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

New-Item -ItemType Directory -Force -Path $RuntimeRoot, $LogRoot | Out-Null
Remove-Item $StatusPath, $StatusTemp, $CancelPath -Force -ErrorAction SilentlyContinue

function Write-Status {
    param(
        [string]$Title,
        [int]$Percent,
        [string]$Detail = "",
        [string]$State = "Çalışıyor",
        [bool]$Done = $false,
        [bool]$IsError = $false
    )
    $script:LastPercent = [Math]::Max($script:LastPercent, [Math]::Max(0, [Math]::Min(100, $Percent)))
    $stamp = Get-Date -Format "HH:mm:ss"
    $line = "[$stamp] [INFO] $Title"
    if ($Detail) { $line += " — $Detail" }
    $script:LauncherLines.Add($line)
    while ($script:LauncherLines.Count -gt 80) { $script:LauncherLines.RemoveAt(0) }
    Add-Content -Path $LauncherLog -Value $line -Encoding UTF8

    $payload = [ordered]@{
        title = $Title
        detail = $Detail
        percent = $script:LastPercent
        state = $State
        done = $Done
        error = $IsError
        logs = @($script:LauncherLines)
    } | ConvertTo-Json -Depth 4 -Compress
    [System.IO.File]::WriteAllText($StatusTemp, $payload, $Utf8NoBom)
    Move-Item -Path $StatusTemp -Destination $StatusPath -Force
}

function Test-LauncherCancel {
    if (Test-Path $CancelPath) {
        throw "Başlatma kullanıcı tarafından durduruldu."
    }
}

function Start-LauncherWindow {
    if (-not (Test-Path $LauncherWindow)) { return }
    $args = @(
        "-NoLogo", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass",
        "-File", "`"$LauncherWindow`"",
        "-StatusPath", "`"$StatusPath`"",
        "-CancelPath", "`"$CancelPath`"",
        "-LogPath", "`"$LauncherLog`""
    )
    $script:WindowProcess = Start-Process -FilePath "powershell.exe" -ArgumentList $args -PassThru
}

function Ensure-AuroraOverhaul {
    $index = Join-Path $AppRoot "web\index.html"
    if (-not (Test-Path $index)) { return }

    $html = [System.IO.File]::ReadAllText($index, [System.Text.Encoding]::UTF8)
    $cssTag = '<link rel="stylesheet" href="./aurora-overhaul.css?v=3" />'
    $jsTag = '<script src="./aurora-overhaul.js?v=3" defer></script>'

    if ($html -match '<link rel="stylesheet" href="\./aurora-overhaul\.css(?:\?v=\d+)?"\s*/>') {
        $html = [regex]::Replace($html, '<link rel="stylesheet" href="\./aurora-overhaul\.css(?:\?v=\d+)?"\s*/>', $cssTag)
    } else {
        $html = $html.Replace(
            '<link rel="stylesheet" href="./styles.css" />',
            '<link rel="stylesheet" href="./styles.css" />' + [Environment]::NewLine + "    $cssTag"
        )
    }

    if ($html -match '<script src="\./aurora-overhaul\.js(?:\?v=\d+)?"\s+defer></script>') {
        $html = [regex]::Replace($html, '<script src="\./aurora-overhaul\.js(?:\?v=\d+)?"\s+defer></script>', $jsTag)
    } else {
        $html = $html.Replace(
            '<script src="./app.js" defer></script>',
            '<script src="./app.js" defer></script>' + [Environment]::NewLine + "    $jsTag"
        )
    }

    [System.IO.File]::WriteAllText($index, $html, $Utf8NoBom)
}

function Invoke-Logged([string]$File, [string[]]$Arguments) {
    Test-LauncherCancel
    & $File @Arguments 2>&1 | Out-File -FilePath $LauncherLog -Append -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { throw "Komut tamamlanamadı: $File" }
    Test-LauncherCancel
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
    Write-Status "EchoWraith hazırlanıyor" 2 "Grafik başlatıcı açılıyor."
    Start-LauncherWindow
    Start-Sleep -Milliseconds 350
    Test-LauncherCancel

    Write-Status "Aurora arayüzü bağlanıyor" 8 "Yeni kütüphane, indirme, izleme ve çalışma alanı etkinleştiriliyor."
    Ensure-AuroraOverhaul

    Write-Status "Python çalışma motoru denetleniyor" 16 "Uyumlu yerel Python sürümü aranıyor."
    $Python = $null
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $Python = Test-Python "py" @("-3.12")
        if (-not $Python) { $Python = Test-Python "py" @("-3.11") }
        if (-not $Python) { $Python = Test-Python "py" @("-3") }
    }
    if (-not $Python -and (Get-Command python -ErrorAction SilentlyContinue)) {
        $Python = Test-Python "python"
    }
    Test-LauncherCancel

    if (-not $Python) {
        Write-Status "Python otomatik kuruluyor" 24 "Yalnızca kullanıcı hesabına kurulacak."
        $Installer = Join-Path $RuntimeRoot "python-installer.exe"
        $PythonUrl = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
        Invoke-WebRequest -Uri $PythonUrl -OutFile $Installer -UseBasicParsing
        Test-LauncherCancel
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
        Write-Status "İlk kullanım ortamı oluşturuluyor" 34 "Bu adım yalnızca ilk açılışta yapılır."
        & $Python.File @($Python.Prefix) -m venv $VenvRoot
        if ($LASTEXITCODE -ne 0) { throw "Yerel çalışma ortamı oluşturulamadı." }
    }
    Test-LauncherCancel
    Write-Status "Yerel çalışma ortamı hazır" 43 "Gerekli modüller doğrulanıyor."

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
    Test-LauncherCancel
    Write-Status "Bileşen sağlığı denetlendi" 54 "Eksik veya bozuk paketler otomatik onarılacak."

    if ($CurrentHash -ne $SavedHash -or -not $RuntimeHealthy) {
        if ($SavedHash -and -not $RuntimeHealthy) {
            Write-Status "Eksik bileşenler onarılıyor" 60 "Güvenli otomatik onarım uygulanıyor."
        }
        Write-Status "Gerekli paketler kuruluyor" 66 "Ayrıntılar launcher.log dosyasına yazılıyor."
        Invoke-Logged $VenvPython @("-m", "pip", "install", "--upgrade", "pip", "wheel")
        Invoke-Logged $VenvPython @("-m", "pip", "install", "--prefer-binary", "-r", $Requirements)
        Write-Status "Tarayıcı motoru hazırlanıyor" 79 "Arka plan ders taraması için Chromium doğrulanıyor."
        Invoke-Logged $VenvPython @("-m", "playwright", "install", "chromium")
        Write-Status "Video araçları hazırlanıyor" 89 "FFmpeg bileşenleri doğrulanıyor."
        Invoke-Logged $VenvPython @("-c", "from static_ffmpeg import run; print(run.get_or_fetch_platform_executables_else_raise())")
        Set-Content -Path $Marker -Value $CurrentHash -Encoding ASCII
    } else {
        Write-Status "Tüm bileşenler güncel" 89 "Yeniden kurulum gerekmiyor."
    }

    Test-LauncherCancel
    Write-Status "Luna paneli açıyor" 96 "Yerel sunucu başlatılıyor."
    $ServerScript = Join-Path $AppRoot "echowraith_server.py"
    Start-Process -FilePath $VenvPythonW -ArgumentList "`"$ServerScript`"" -WorkingDirectory $AppRoot
    Start-Sleep -Milliseconds 950
    Write-Status "EchoWraith hazır" 100 "Panel tarayıcıda açıldı." "Hazır" $true $false
    Start-Sleep -Milliseconds 1500
    Remove-Item $CancelPath -Force -ErrorAction SilentlyContinue
    exit 0
} catch {
    $message = $_.Exception.Message
    $stamp = Get-Date -Format "HH:mm:ss"
    $errorLine = "[$stamp] [ERROR] $message"
    $script:LauncherLines.Add($errorLine)
    Add-Content -Path $LauncherLog -Value "FATAL: $message`n$($_.ScriptStackTrace)" -Encoding UTF8
    Write-Status "EchoWraith başlatılamadı" $script:LastPercent $message "Hata" $false $true
    Start-Sleep -Milliseconds 300
    if (-not $script:WindowProcess -or $script:WindowProcess.HasExited) {
        try { Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show("EchoWraith başlatılamadı.`n`n$message`n`nLog: $LauncherLog", "EchoWraith - Hata") | Out-Null } catch { }
    }
    exit 1
}
