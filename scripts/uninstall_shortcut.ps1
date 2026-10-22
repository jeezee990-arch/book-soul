# Uninstall Book Soul desktop + Start Menu shortcuts.
# Usage: powershell -ExecutionPolicy Bypass -File scripts/uninstall_shortcut.ps1

$ErrorActionPreference = 'Stop'

$desktopDir = [Environment]::GetFolderPath("Desktop")
$startMenu  = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs\Book Soul"

$paths = @(
    (Join-Path $desktopDir "Book Soul.lnk"),
    (Join-Path $startMenu "Book Soul.lnk")
)

foreach ($p in $paths) {
    if (Test-Path $p) {
        Remove-Item $p -Verbose
    } else {
        Write-Host "  (skip) $p not found"
    }
}

# Clean empty Start Menu dir
if ((Test-Path $startMenu) -and -not (Get-ChildItem $startMenu)) {
    Remove-Item $startMenu -Recurse -Verbose
}

Write-Host ""
Write-Host "Done."