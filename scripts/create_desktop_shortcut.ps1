# Create "Book Soul" desktop shortcut (double-click to launch).
#
# Idempotent: if shortcut exists, replace it.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\create_desktop_shortcut.ps1

$ErrorActionPreference = 'Stop'

$RepoRoot   = (Split-Path -Parent (Split-Path -Parent $PSCommandPath))
$Target     = Join-Path $RepoRoot 'Start Book Soul.vbs'
$WorkingDir = $RepoRoot
$ShortcutPath = [Environment]::GetFolderPath('Desktop') + '\Book Soul.lnk'

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Target
$Shortcut.WorkingDirectory = $WorkingDir
$Shortcut.IconLocation = "$RepoRoot\apps\desktop\src-tauri\icons\32x32.png"
$Shortcut.Description = "Book Soul - AI-assisted novel writing"
$Shortcut.WindowStyle = 7  # Minimized; the launcher hides its own window
$Shortcut.Save()

Write-Host "[ok] Desktop shortcut created: $ShortcutPath"
Write-Host "     Target: $Target"
Write-Host "     Working dir: $WorkingDir"
