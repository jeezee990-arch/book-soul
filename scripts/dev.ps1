<#
.SYNOPSIS
  Book Soul one-shot dev launcher: Python backend + Tauri desktop

.DESCRIPTION
  1. Pre-flight: verify Python venv / node_modules / cargo are ready
  2. Start Python FastAPI in server/ (127.0.0.1:8765)
  3. Wait until /ping is ready (max 30s)
  4. Start pnpm tauri dev in apps/desktop/
  5. When Tauri exits (Ctrl+C or window close), stop Python too

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
$DevDataDir = Join-Path $RepoRoot 'data\dev'

# ===== Pre-flight =====
$fail = $false
if (-not (Test-Path $PythonExe)) {
    Write-Host "[X] Python venv missing: $PythonExe" -ForegroundColor Red
    Write-Host "    Fix: cd server && uv sync --extra dev" -ForegroundColor Yellow
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

if (-not (Test-Path $DevDataDir)) {
    New-Item -ItemType Directory -Path $DevDataDir | Out-Null
}
$env:BOOK_SOUL_DATA_DIR = $DevDataDir

# Header
Write-Host ""
Write-Host "============================================" -ForegroundColor Magenta
Write-Host "  Book Soul Dev Launcher" -ForegroundColor Magenta
Write-Host "  Repo: $RepoRoot" -ForegroundColor DarkGray
Write-Host "  Data: $DevDataDir" -ForegroundColor DarkGray
Write-Host "============================================" -ForegroundColor Magenta
Write-Host ""

# Kill any stale Python holding port 8765
$PortOwners = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
foreach ($Conn in $PortOwners) {
    $OldProc = Get-Process -Id $Conn.OwningProcess -ErrorAction SilentlyContinue
    if ($OldProc -and $OldProc.ProcessName -eq "python") {
        Write-Host "[!] Killing stale Python PID $($OldProc.Id) on 8765" -ForegroundColor Yellow
        Stop-Process -Id $OldProc.Id -Force
    }
}
Start-Sleep -Seconds 1

# ===== Step 1: Start Python backend =====
Write-Host "[1/3] Starting Python backend ($BackendUrl)..." -ForegroundColor Cyan

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
Write-Host "       Python PID: $($PythonProc.Id)" -ForegroundColor DarkGray

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
    Write-Host "[X] Backend not ready in ${MaxWaitSec}s. Check log:" -ForegroundColor Red
    Write-Host "    $PythonErr" -ForegroundColor Yellow
    try { Stop-Process -Id $PythonProc.Id -Force -ErrorAction SilentlyContinue } catch {}
    exit 1
}

# ===== Step 3: Start Tauri (blocks) =====
Write-Host "[3/3] Starting Tauri (apps/desktop/)..." -ForegroundColor Cyan
Write-Host ""
Write-Host "--------------------------------------------" -ForegroundColor DarkGray
Write-Host "  Python ready (PID $($PythonProc.Id))" -ForegroundColor Green
Write-Host "  Tauri starting... close window to stop both" -ForegroundColor Yellow
Write-Host "--------------------------------------------" -ForegroundColor DarkGray
Write-Host ""

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