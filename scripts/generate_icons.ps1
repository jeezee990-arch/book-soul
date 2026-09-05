# Generate Book Soul app icons (Phase 8.1 升级版)
# 用 PowerShell + System.Drawing 生成多尺寸 PNG
# 设计：深蓝渐变背景 + 白色书本 + 紫色灵魂火焰

$ErrorActionPreference = 'Stop'
$iconDir = Join-Path $PSScriptRoot "..\apps\desktop\src-tauri\icons"
$iconDir = (Resolve-Path $iconDir).Path

Add-Type -AssemblyName System.Drawing

function New-IconPng([int]$Size, [string]$OutPath) {
    $bmp = New-Object System.Drawing.Bitmap $Size, $Size
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = 'AntiAlias'
    $g.TextRenderingHint = 'AntiAlias'

    # 背景：圆角矩形 + 线性渐变（深蓝→深紫）
    $rect = New-Object System.Drawing.Rectangle 0, 0, $Size, $Size
    $lgBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush $rect, ([System.Drawing.Color]::FromArgb(255, 15, 23, 42)), ([System.Drawing.Color]::FromArgb(255, 76, 29, 149)), 45.0
    $g.FillRectangle($lgBrush, $rect)

    # 圆角蒙版：用 GraphicsPath 裁切
    $cornerRadius = [int]($Size * 0.18)
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $path.AddArc(0, 0, $cornerRadius * 2, $cornerRadius * 2, 180, 90)
    $path.AddArc($Size - $cornerRadius * 2, 0, $cornerRadius * 2, $cornerRadius * 2, 270, 90)
    $path.AddArc($Size - $cornerRadius * 2, $Size - $cornerRadius * 2, $cornerRadius * 2, $cornerRadius * 2, 0, 90)
    $path.AddArc(0, $Size - $cornerRadius * 2, $cornerRadius * 2, $cornerRadius * 2, 90, 90)
    $path.CloseFigure()
    $g.SetClip($path)
    $g.FillRectangle($lgBrush, $rect)
    $g.ResetClip()

    # 书本（白色矩形 + 中线）
    $bookW = [int]($Size * 0.5)
    $bookH = [int]($Size * 0.42)
    $bookX = [int](($Size - $bookW) / 2)
    $bookY = [int]($Size * 0.45)
    $bookBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 248, 250, 252))
    $g.FillRectangle($bookBrush, $bookX, $bookY, $bookW, $bookH)
    # 中线
    $linePen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(255, 148, 163, 184)), [int][Math]::Max(1, $Size / 128)
    $g.DrawLine($linePen, [int]($bookX + $bookW / 2), $bookY, [int]($bookX + $bookW / 2), [int]($bookY + $bookH))
    # 左侧书页线
    for ($i = 1; $i -le 4; $i++) {
        $ly = $bookY + [int]($bookH * $i / 5)
        $lStart1 = $bookX + [int]($bookW * 0.05)
        $lEnd1 = $bookX + [int]($bookW * 0.4)
        $lStart2 = $bookX + [int]($bookW * 0.6)
        $lEnd2 = $bookX + [int]($bookW * 0.95)
        $g.DrawLine($linePen, $lStart1, $ly, $lEnd1, $ly)
        $g.DrawLine($linePen, $lStart2, $ly, $lEnd2, $ly)
    }

    # 灵魂火焰（紫色外 + 粉色内 + 高光）
    $flameCx = [int]($Size / 2)
    $flameCy = [int]($Size * 0.30)
    $flameR = [int]($Size * 0.20)
    $flameRect = New-Object System.Drawing.Rectangle ($flameCx - $flameR), ($flameCy - $flameR), ($flameR * 2), ($flameR * 2)
    $flameColor1 = [System.Drawing.Color]::FromArgb(255, 244, 114, 182)
    $flameColor2 = [System.Drawing.Color]::FromArgb(255, 168, 85, 247)
    $flameBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush($flameRect, $flameColor1, $flameColor2, 90.0)
    $g.FillEllipse($flameBrush, $flameRect)
    # 内焰
    $innerR = [int]($flameR * 0.55)
    $innerBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 253, 230, 243))
    $g.FillEllipse($innerBrush, ($flameCx - $innerR), ($flameCy - $innerR), ($innerR * 2), ($innerR * 2))
    # 高光
    $hlR = [int]($innerR * 0.3)
    $g.FillEllipse([System.Drawing.Brushes]::White, ($flameCx - $hlR - 2), ($flameCy - $hlR - 2), ($hlR * 2), ($hlR * 2))

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
