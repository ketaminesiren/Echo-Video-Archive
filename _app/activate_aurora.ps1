$ErrorActionPreference = "Stop"
$index = Join-Path $PSScriptRoot "web\index.html"
if (-not (Test-Path $index)) { exit 0 }

$text = [System.IO.File]::ReadAllText($index)
$changed = $false

if ($text -notmatch 'aurora-overhaul\.css') {
    $text = $text.Replace(
        '<link rel="stylesheet" href="./styles.css" />',
        '<link rel="stylesheet" href="./styles.css" />' + [Environment]::NewLine + '    <link rel="stylesheet" href="./aurora-overhaul.css?v=1" />'
    )
    $changed = $true
}

if ($text -notmatch 'aurora-overhaul\.js') {
    $text = $text.Replace(
        '<script src="./app.js" defer></script>',
        '<script src="./app.js" defer></script>' + [Environment]::NewLine + '    <script src="./aurora-overhaul.js?v=1" defer></script>'
    )
    $changed = $true
}

if ($changed) {
    [System.IO.File]::WriteAllText($index, $text, [System.Text.UTF8Encoding]::new($false))
}
