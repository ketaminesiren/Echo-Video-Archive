$ErrorActionPreference = "Stop"
$index = Join-Path $PSScriptRoot "web\index.html"
if (-not (Test-Path $index)) { exit 0 }

$text = [System.IO.File]::ReadAllText($index, [System.Text.Encoding]::UTF8)
$cssTag = '<link rel="stylesheet" href="./aurora-overhaul.css?v=3" />'
$jsTag = '<script src="./aurora-overhaul.js?v=3" defer></script>'

if ($text -match '<link rel="stylesheet" href="\./aurora-overhaul\.css(?:\?v=\d+)?"\s*/>') {
    $text = [regex]::Replace($text, '<link rel="stylesheet" href="\./aurora-overhaul\.css(?:\?v=\d+)?"\s*/>', $cssTag)
} else {
    $text = $text.Replace(
        '<link rel="stylesheet" href="./styles.css" />',
        '<link rel="stylesheet" href="./styles.css" />' + [Environment]::NewLine + "    $cssTag"
    )
}

if ($text -match '<script src="\./aurora-overhaul\.js(?:\?v=\d+)?"\s+defer></script>') {
    $text = [regex]::Replace($text, '<script src="\./aurora-overhaul\.js(?:\?v=\d+)?"\s+defer></script>', $jsTag)
} else {
    $text = $text.Replace(
        '<script src="./app.js" defer></script>',
        '<script src="./app.js" defer></script>' + [Environment]::NewLine + "    $jsTag"
    )
}

[System.IO.File]::WriteAllText($index, $text, [System.Text.UTF8Encoding]::new($false))
