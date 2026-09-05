# Install desktop + Start Menu shortcuts for Book Soul
# Usage: powershell -ExecutionPolicy Bypass -File scripts/install_shortcut.ps1
# Creates:
#   - Desktop\Book Soul.lnk
#   - Start Menu\Programs\Book Soul\Book Soul.lnk

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$startBat = Join-Path $projectRoot "start.bat"
$iconPng = Join-Path $projectRoot "apps\desktop\src-tauri\icons\icon.png"

if (-not (Test-Path $startBat)) {
    throw "start.bat not found at $startBat"
}
if (-not (Test-Path $iconPng)) {
    Write-Warning "icon.png not found at $iconPng; using default"
    $iconPng = $null
}

function New-Shortcut([string]$ShortcutPath, [string]$TargetPath, [string]$WorkingDir, [string]$IconPath, [string]$Description) {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($ShortcutPath)
    $shortcut.TargetPath = $TargetPath
    $shortcut.WorkingDirectory = $WorkingDir
    if ($IconPath) {
        $shortcut.IconLocation = $IconPath
    }
    $shortcut.Description = $Description
    $shortcut.WindowStyle = 7  # 最小化启动（避免黑窗闪一下）
    $shortcut.Save()
    Write-Host "  -> $ShortcutPath"
}

$desktopDir = [Environment]::GetFolderPath("Desktop")
$startMenu = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs\Book Soul"
if (-not (Test-Path $startMenu)) {
    New-Item -ItemType Directory -Path $startMenu -Force | Out-Null
}

Write-Host "Creating shortcuts..."
New-Shortcut `
    -ShortcutPath (Join-Path $desktopDir "Book Soul.lnk") `
    -TargetPath $startBat `
    -WorkingDir $projectRoot `
    -IconPath $iconPng `
    -Description "Book Soul - AI 辅助小说写作"

New-Shortcut `
    -ShortcutPath (Join-Path $startMenu "Book Soul.lnk") `
    -TargetPath $startBat `
    -WorkingDir $projectRoot `
    -IconPath $iconPng `
    -Description "Book Soul - AI 辅助小说写作"

Write-Host "Done!"
Write-Host ""
Write-Host "Tip: Double-click 'Book Soul' on Desktop / Start Menu to launch"
