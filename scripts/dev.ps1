<#
.SYNOPSIS
    Book Soul 开发模式启动器（带可见控制台，便于看日志）。

.DESCRIPTION
    和 launcher_hidden.ps1 的区别：
      - dev.ps1          → 可见控制台，给开发者看日志用
      - launcher_hidden.ps1 → 零控制台，给"当成独立软件用"的人

    启动流程（刻意保持极简）：
      1. 环境自检（.venv / node_modules / cargo）—— 缺什么就明说，不猜
      2. pnpm tauri dev
         ├─ beforeDevCommand 自动拉起 Python 后端（127.0.0.1:8765）
         ├─ Vite 起前端
         └─ Rust 侧复用/拉起后端，随机端口分配给前端

    后端端口不需要手工管理：Rust 侧会先看 8765 有没有"本项目"的后端，
    有就复用（保证每次 dev 都是最新代码），没有就用自己的随机端口。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1
#>

$ErrorActionPreference = 'Stop'

$ScriptDir  = Split-Path -Parent $PSCommandPath
$RepoRoot   = (Resolve-Path (Join-Path $ScriptDir '..')).Path
$DesktopDir = Join-Path $RepoRoot 'apps\desktop'
$PythonExe  = Join-Path $RepoRoot '.venv\Scripts\python.exe'

# ===== Pre-flight =====
$fail = $false
if (-not (Test-Path $PythonExe)) {
    Write-Host "[X] Python venv missing: $PythonExe" -ForegroundColor Red
    Write-Host "    Fix: uv sync" -ForegroundColor Yellow
    $fail = $true
}
if (-not (Test-Path (Join-Path $DesktopDir 'node_modules'))) {
    Write-Host "[X] node_modules missing: $DesktopDir\node_modules" -ForegroundColor Red
    Write-Host "    Fix: cd apps\desktop && pnpm install" -ForegroundColor Yellow
    $fail = $true
}
# Ensure rustup-managed cargo is on PATH (Tauri needs it)
$CargoBin = Join-Path $env:USERPROFILE '.cargo\bin'
if (Test-Path (Join-Path $CargoBin 'cargo.exe')) {
    $env:PATH = "$CargoBin;$env:PATH"
} else {
    Write-Host "[X] cargo not found at $CargoBin" -ForegroundColor Red
    Write-Host "    Fix: Install Rust from https://rustup.rs/" -ForegroundColor Yellow
    $fail = $true
}
if ($fail) { exit 1 }

$DevDataDir = Join-Path $RepoRoot 'data\dev'
if (-not (Test-Path $DevDataDir)) {
    New-Item -ItemType Directory -Path $DevDataDir | Out-Null
}
$env:BOOK_SOUL_DATA_DIR = $DevDataDir

Write-Host ""
Write-Host "============================================" -ForegroundColor Magenta
Write-Host "  Book Soul Dev Launcher" -ForegroundColor Magenta
Write-Host "  Repo: $RepoRoot" -ForegroundColor DarkGray
Write-Host "  Data: $DevDataDir" -ForegroundColor DarkGray
Write-Host "============================================" -ForegroundColor Magenta
Write-Host ""

# ===== 启动 Tauri（阻塞，直到窗口关闭）=====
$DesktopExitCode = 0
Push-Location -LiteralPath $DesktopDir
try {
    & pnpm tauri dev
    $DesktopExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Tauri exited (code $DesktopExitCode)." -ForegroundColor Yellow
exit $DesktopExitCode
