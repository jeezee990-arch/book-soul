# Install desktop + Start Menu shortcuts for Book Soul.
# Usage: powershell -ExecutionPolicy Bypass -File scripts/install_shortcut.ps1
# Creates:
#   - Desktop\Book Soul.lnk
#   - Start Menu\Programs\Book Soul\Book Soul.lnk
# Target: scripts\launcher.vbs (zero-console, like a real desktop app)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$launcher    = Join-Path $projectRoot "scripts\launcher.vbs"
$iconPng     = Join-Path $projectRoot "apps\desktop\src-tauri\icons\icon.png"

if (-not (Test-Path $launcher)) {
    throw "Launcher not found: $launcher"
}
if (-not (Test-Path $iconPng)) {
    Write-Warning "icon.png not found at $iconPng; using default Windows icon"
    $iconPng = $null
}

function New-Shortcut([string]$ShortcutPath, [string]$TargetPath, [string]$WorkingDir, [string]$IconPath, [string]$Description) {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($ShortcutPath)
    # Direct invocation: wscript.exe launcher.vbs <root> — no PowerShell window
    $shortcut.TargetPath = "wscript.exe"
    $shortcut.Arguments = "`"$TargetPath`" `"$WorkingDir`""
    $shortcut.WorkingDirectory = $WorkingDir
    if ($IconPath) {
        $shortcut.IconLocation = $IconPath
    }
    $shortcut.Description = $Description
    $shortcut.WindowStyle = 7  # Hidden; vbs exits immediately, only Tauri window remains
    $shortcut.Save()
    Write-Host "  -> $ShortcutPath"
}

$desktopDir = [Environment]::GetFolderPath("Desktop")
$startMenu  = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs\Book Soul"
if (-not (Test-Path $startMenu)) {
    New-Item -ItemType Directory -Path $startMenu -Force | Out-Null
}

Write-Host "Creating shortcuts (target = scripts\launcher.vbs, zero-console)..."
New-Shortcut `
    -ShortcutPath (Join-Path $desktopDir "Book Soul.lnk") `
    -TargetPath $launcher `
    -WorkingDir $projectRoot `
    -IconPath $iconPng `
    -Description "Book Soul - AI 辅助小说写作"

New-Shortcut `
    -ShortcutPath (Join-Path $startMenu "Book Soul.lnk") `
    -TargetPath $launcher `
    -WorkingDir $projectRoot `
    -IconPath $iconPng `
    -Description "Book Soul - AI 辅助小说写作"

Write-Host ""
Write-Host "Done! Double-click 'Book Soul' on Desktop / Start Menu to launch."
Write-Host "(No console will appear; only the Book Soul window will open.)"
Write-Host ""
Write-Host "Tip: To uninstall, run scripts\uninstall_shortcut.ps1"