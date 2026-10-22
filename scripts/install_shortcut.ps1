<#
.SYNOPSIS
    为 Book Soul 创建桌面 + 开始菜单快捷方式。

.DESCRIPTION
    快捷方式的目标按优先级选择：

      1. **独立版 exe**（dist\Book Soul\Book Soul.exe）
         —— 直接指向 exe。双击快捷方式和双击软件完全一样，
            没有控制台、没有中间脚本，最接近真正的独立软件。
      2. **构建产物 exe**（src-tauri\target\release\*.exe）
      3. **回退**到 wscript.exe scripts\launcher.vbs
         —— 没有构建产物时也能启动（走开发模式）。

    用法：
        powershell -ExecutionPolicy Bypass -File scripts\install_shortcut.ps1
        powershell -ExecutionPolicy Bypass -File scripts\install_shortcut.ps1 -Force
            -Force 强制重新指向独立版（即使之前已经指向过）
#>

param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$IconIco     = Join-Path $ProjectRoot "apps\desktop\src-tauri\icons\icon.ico"
$LauncherVbs = Join-Path $ProjectRoot "scripts\launcher.vbs"

function Get-StandaloneExe {
    <#
      返回打包好的应用 exe（排除 sidecar 本体）；找不到返回 $null。
      与 launcher_hidden.ps1 里的同名函数保持一致的查找顺序。
    #>
    $candidates = @(
        (Join-Path $ProjectRoot 'dist\Book Soul'),
        (Join-Path $ProjectRoot 'apps\desktop\src-tauri\target\release')
    )
    foreach ($dir in $candidates) {
        if (-not (Test-Path $dir)) { continue }
        $hit = Get-ChildItem -Path $dir -Filter '*.exe' -File -ErrorAction SilentlyContinue |
               Where-Object { $_.Name -notlike 'book-soul-server*' } |
               Sort-Object Length -Descending |
               Select-Object -First 1
        if ($hit) { return $hit.FullName }
    }
    return $null
}

$standalone = Get-StandaloneExe

if ($standalone) {
    $target = $standalone
    $args = ''
    $workDir = Split-Path -Parent $standalone
    $mode = 'standalone'
} else {
    if (-not (Test-Path $LauncherVbs)) {
        throw "Launcher not found: $LauncherVbs"
    }
    $target = 'wscript.exe'
    $args = '"' + $LauncherVbs + '"'
    $workDir = $ProjectRoot
    $mode = 'dev fallback'
}

function New-Shortcut([string]$ShortcutPath, [string]$TargetPath, [string]$Arguments, [string]$WorkingDir, [string]$IconPath, [string]$Description) {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($ShortcutPath)
    $shortcut.TargetPath = $TargetPath
    if ($Arguments) { $shortcut.Arguments = $Arguments }
    $shortcut.WorkingDirectory = $WorkingDir
    if ($IconPath -and (Test-Path $IconPath)) {
        $shortcut.IconLocation = $IconPath
    }
    $shortcut.Description = $Description
    $shortcut.WindowStyle = 7  # Minimized/no console flash; standalone exe never shows one
    $shortcut.Save()
    Write-Host "  -> $ShortcutPath"
}

$desktopDir = [Environment]::GetFolderPath("Desktop")
$startMenu  = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs\Book Soul"
if (-not (Test-Path $startMenu)) {
    New-Item -ItemType Directory -Path $startMenu -Force | Out-Null
}

$desktopLnk = Join-Path $desktopDir "Book Soul.lnk"
$startLnk   = Join-Path $startMenu "Book Soul.lnk"

# 已经指向独立版就别重复覆盖（除非 -Force）
if (-not $Force -and $mode -eq 'standalone') {
    $existing = Get-ChildItem -Path $startLnk -ErrorAction SilentlyContinue
    if ($existing) {
        $shell = New-Object -ComObject WScript.Shell
        $sc = $shell.CreateShortcut($startLnk)
        if ($sc.TargetPath -eq $target) {
            Write-Host "Shortcut already points to standalone build. Use -Force to redo."
            Write-Host "  Target: $target"
            exit 0
        }
    }
}

Write-Host "Creating shortcuts (mode: $mode)..."
Write-Host "  Target: $target $args"

New-Shortcut -ShortcutPath $desktopLnk -TargetPath $target -Arguments $args `
             -WorkingDir $workDir -IconPath $IconIco -Description "Book Soul - AI 辅助小说写作"
New-Shortcut -ShortcutPath $startLnk   -TargetPath $target -Arguments $args `
             -WorkingDir $workDir -IconPath $IconIco -Description "Book Soul - AI 辅助小说写作"

Write-Host ""
if ($mode -eq 'standalone') {
    Write-Host "Done! Double-click 'Book Soul' to launch the standalone app." -ForegroundColor Green
    Write-Host "Data folder: $(Join-Path $workDir 'data')"
} else {
    Write-Host "Done! Shortcut points to the dev launcher (no standalone build found)." -ForegroundColor Yellow
    Write-Host "Build one with: powershell -ExecutionPolicy Bypass -File scripts\build_standalone.ps1"
}
Write-Host ""
Write-Host "Tip: To uninstall, run scripts\uninstall_shortcut.ps1"
