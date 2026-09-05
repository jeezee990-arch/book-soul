# Generate placeholder PNG icons for Tauri (Phase 8.1)
# Usage: powershell -ExecutionPolicy Bypass -File scripts\generate_icons.ps1
# Output: apps/desktop/src-tauri/icons/{32x32,128x128,128x128@2x,icon}.png

$ErrorActionPreference = 'Stop'
$iconDir = Join-Path $PSScriptRoot "..\apps\desktop\src-tauri\icons"
$iconDir = (Resolve-Path $iconDir).Path

Add-Type -AssemblyName System.Drawing

$dark = [System.Drawing.Color]::FromArgb(255, 31, 41, 55)
$book = [System.Drawing.Color]::FromArgb(255, 226, 232, 240)
$line = [System.Drawing.Color]::FromArgb(255, 148, 163, 184)
$flame = [System.Drawing.Color]::FromArgb(255, 217, 70, 239)
$inner = [System.Drawing.Color]::FromArgb(255, 252, 231, 243)

function New-IconPng([int]$Size, [string]$OutPath) {
    $bmp = New-Object System.Drawing.Bitmap $Size, $Size
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = 'AntiAlias'
    $g.TextRenderingHint = 'AntiAlias'

    $bgBrush = New-Object System.Drawing.SolidBrush $dark
    $g.FillRectangle($bgBrush, 0, 0, $Size, $Size)

    $bookW = [int]($Size * 0.5)
    $bookH = [int]($Size * 0.4)
    $bookX = [int](($Size - $bookW) / 2)
    $bookY = [int](($Size - $bookH) / 2 + $Size * 0.1)
    $bookBrush = New-Object System.Drawing.SolidBrush $book
    $g.FillRectangle($bookBrush, $bookX, $bookY, $bookW, $bookH)
    $lineWidth = [int][Math]::Max(1, $Size / 128)
    $linePen = New-Object System.Drawing.Pen $line, $lineWidth
    $g.DrawLine($linePen, [int]($bookX + $bookW / 2), $bookY, [int]($bookX + $bookW / 2), [int]($bookY + $bookH))

    $flameR = [int]($Size * 0.18)
    $flameCx = [int]($Size / 2)
    $flameCy = [int]($Size * 0.35)
    $flameBrush = New-Object System.Drawing.SolidBrush $flame
    $g.FillEllipse($flameBrush, ($flameCx - $flameR), ($flameCy - $flameR), ($flameR * 2), ($flameR * 2))
    $innerR = [int]($flameR * 0.6)
    $innerBrush = New-Object System.Drawing.SolidBrush $inner
    $g.FillEllipse($innerBrush, ($flameCx - $innerR), ($flameCy - $innerR), ($innerR * 2), ($innerR * 2))

    $g.Dispose()
    $bmp.Save($OutPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Write-Host ("  -> " + $OutPath)
}

$sizes = @{
    "32x32.png" = 32
    "128x128.png" = 128
    "128x128@2x.png" = 256
    "icon.png" = 512
}

Write-Host "Generating PNG icons..."
foreach ($kv in $sizes.GetEnumerator()) {
    $out = Join-Path $iconDir $kv.Key
    New-IconPng -Size $kv.Value -OutPath $out
}

Write-Host "Done!"
