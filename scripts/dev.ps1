<#
.SYNOPSIS
  Book Soul one-shot dev launcher: Python backend + Tauri desktop

.DESCRIPTION
  1. Start Python FastAPI in server/ (127.0.0.1:8765)
  2. Wait until /ping is ready
  3. Start pnpm tauri dev in apps/desktop/
  4. When Tauri exits (Ctrl+C), stop Python too

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1
#>

$ErrorActionPreference = 'Stop'

# Resolve paths (script lives in scripts/, repo root is its parent)
$ScriptDir  = Split-Path -Parent $PSCommandPath
$RepoRoot   = Split-Path -Parent $ScriptDir
$ServerDir  = Join-Path $RepoRoot 'server'
$DesktopDir = Join-Path $RepoRoot 'apps\desktop'
$PythonExe  = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$BackendUrl = 'http://127.0.0.1:8765'
$LogDir     = $env:TEMP

# Pre-flight checks
if (-not (Test-Path $PythonExe)) {
    Write-Error "[X] Python not found: $PythonExe. Run 'uv pip install -e .[dev]' in server/ first."
}
if (-not (Test-Path (Join-Path $DesktopDir 'node_modules'))) {
    Write-Error "[X] node_modules missing: $DesktopDir\node_modules. Run 'pnpm install' in apps/desktop/ first."
}

# Ensure rustup-managed cargo is on PATH (Tauri needs it)
$CargoBin = Join-Path $env:USERPROFILE '.cargo\bin'
if (Test-Path (Join-Path $CargoBin 'cargo.exe')) {
    $env:PATH = "$CargoBin;$env:PATH"
    Write-Host "       cargo PATH: $CargoBin" -ForegroundColor DarkGray
} else {
    Write-Error "[X] cargo not found at $CargoBin. Install Rust: https://rustup.rs/"
}

# ===== Step 1: Start Python backend =====
Write-Host "[1/3] Starting Python backend ($BackendUrl)..." -ForegroundColor Cyan

# 隔离 dev 数据目录：避免污染 ~/Documents/BookSoul
$DevDataDir = Join-Path $RepoRoot 'data\dev'
if (-not (Test-Path $DevDataDir)) {
    New-Item -ItemType Directory -Path $DevDataDir | Out-Null
    Write-Host "       Created data dir: $DevDataDir" -ForegroundColor DarkGray
}
$env:BOOK_SOUL_DATA_DIR = $DevDataDir
Write-Host "       BOOK_SOUL_DATA_DIR=$DevDataDir" -ForegroundColor DarkGray

# 启动前先杀端口 8765 上的 Python 进程（避免老进程占着端口导致新进程启动失败）
$PortOwners = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
foreach ($Conn in $PortOwners) {
    $OldProc = Get-Process -Id $Conn.OwningProcess -ErrorAction SilentlyContinue
    if ($OldProc -and $OldProc.ProcessName -eq "python") {
        Write-Host "       Killing stale Python PID $($OldProc.Id) on port 8765" -ForegroundColor Yellow
        Stop-Process -Id $OldProc.Id -Force
    }
}
Start-Sleep -Seconds 1

$PythonLog = Join-Path $LogDir 'book-soul-backend.out.log'
$PythonErr = Join-Path $LogDir 'book-soul-backend.err.log'
# PowerShell 5.1 Start-Process doesn't reliably inherit $env: vars.
# Use cmd.exe /c "set X=Y && program" to guarantee env is set for child.
$CmdArgs = '/c', "set `"BOOK_SOUL_DATA_DIR=$DevDataDir`" && `"$PythonExe`" -m src.main"
$PythonProc = Start-Process `
    -FilePath "cmd.exe" `
    -ArgumentList $CmdArgs `
    -WorkingDirectory $ServerDir `
    -PassThru `
    -WindowStyle Hidden `
    -RedirectStandardOutput $PythonLog `
    -RedirectStandardError $PythonErr

Write-Host "       Python PID: $($PythonProc.Id)"

# ===== Step 2: Wait for /ping =====
Write-Host "[2/3] Waiting for /ping ..." -ForegroundColor Cyan
$MaxWaitSec = 30
$Waited = 0
$Ready = $false
while ($Waited -lt $MaxWaitSec) {
    Start-Sleep -Seconds 1
    $Waited++
    try {
        $resp = Invoke-WebRequest -Uri "$BackendUrl/ping" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($resp.StatusCode -eq 200) {
            Write-Host "       Ready in ${Waited}s" -ForegroundColor Green
            $Ready = $true
            break
        }
    } catch {
        # still starting
    }
}
if (-not $Ready) {
    Write-Error "[X] Backend not ready in ${MaxWaitSec}s. Check log: $PythonErr"
}

# ===== Step 3: Start Tauri (blocks) =====
Write-Host "[3/3] Starting Tauri (apps/desktop/)..." -ForegroundColor Cyan
Write-Host ""
Write-Host "============================================" -ForegroundColor Magenta
Write-Host "  Python ready  (PID $($PythonProc.Id))" -ForegroundColor Green
Write-Host "  Tauri starting ... Ctrl+C stops both" -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Magenta
Write-Host ""

# Use & (call operator) so PowerShell resolves pnpm.cmd / pnpm.ps1 on PATH
$DesktopExitCode = 0
Push-Location -LiteralPath $DesktopDir
try {
    & pnpm tauri dev
    $DesktopExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}

# Tauri exited -> stop Python
Write-Host ""
Write-Host "Tauri exited (code $DesktopExitCode), stopping Python..." -ForegroundColor Yellow
try {
    Stop-Process -Id $PythonProc.Id -Force -ErrorAction SilentlyContinue
    Write-Host "Python stopped" -ForegroundColor Green
} catch {
    Write-Warning "Failed to stop Python: $_"
}

exit $DesktopExitCode
