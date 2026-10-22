# Book Soul hidden launcher (called by launcher.vbs).
# This is run via wscript.exe with hidden windowStyle.
#
# Workflow:
#   1. Pre-flight: venv / node_modules / cargo (just warn, do not abort)
#   2. Kill stale python on port 8765
#   3. Start python (hidden cmd.exe, logs to file)
#   4. Wait for /ping
#   5. Start `pnpm tauri dev` (this becomes the foreground user-facing window)
#   6. On Tauri exit, stop python

$ErrorActionPreference = 'Stop'

# Resolve project root from this script's location: <root>/scripts/launcher_hidden.ps1
$ScriptDir = Split-Path -Parent $PSCommandPath
$Root      = (Resolve-Path (Join-Path $ScriptDir '..')).Path

# Dev data dir (overrideable via env)
$Dev = if ($env:BOOK_SOUL_DATA_DIR) { $env:BOOK_SOUL_DATA_DIR } else { Join-Path $Root 'data\dev' }
if (-not (Test-Path $Dev)) { New-Item -ItemType Directory -Path $Dev | Out-Null }
$env:BOOK_SOUL_DATA_DIR = $Dev

# ---- Pre-flight warnings (do NOT abort; user might be debugging) ----
if (-not (Test-Path (Join-Path $Root '.venv\Scripts\python.exe'))) {
    Write-Host "[!] .venv missing: cd server; uv sync" -ForegroundColor Yellow
}
if (-not (Test-Path (Join-Path $Root 'apps\desktop\node_modules'))) {
    Write-Host "[!] node_modules missing: cd apps\desktop; pnpm install" -ForegroundColor Yellow
}
$cargoBin = Join-Path $env:USERPROFILE '.cargo\bin'
if (Test-Path (Join-Path $cargoBin 'cargo.exe')) {
    $env:PATH = "$cargoBin;$env:PATH"
} else {
    Write-Host "[!] cargo missing: install Rust from https://rustup.rs/" -ForegroundColor Yellow
}

# ---- Kill stale python on port 8765 ----
try {
    Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
        $p = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
        if ($p -and $p.ProcessName -eq 'python') {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        }
    }
} catch {}
Start-Sleep -Milliseconds 300

# ---- Start backend (hidden, log to file) ----
$pyLog = Join-Path $env:TEMP 'book-soul-backend.out.log'
$pyErr = Join-Path $env:TEMP 'book-soul-backend.err.log'
$py    = Join-Path $Root '.venv\Scripts\python.exe'

# Build the inner command line with proper quoting via array form (no shell escaping pain)
$pyArgs = @('-m', 'src.main')
$env:BOOK_SOUL_DATA_DIR = $Dev

$proc = Start-Process -FilePath $py `
                     -ArgumentList $pyArgs `
                     -WorkingDirectory (Join-Path $Root 'server') `
                     -WindowStyle Hidden `
                     -RedirectStandardOutput $pyLog `
                     -RedirectStandardError $pyErr `
                     -PassThru `
                     -UseNewEnvironment:$false

# Inject data dir into the child process environment (PowerShell 5.1 quirk)
# Start-Process with -UseNewEnvironment doesn't reliably inherit $env: vars set after launch.

# ---- Wait for /ping (15s 通常 OK；正常 2-3s 就绪) ----
$ready = $false
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 1
    try {
        $r = Invoke-WebRequest 'http://127.0.0.1:8765/ping' -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
}
if (-not $ready) {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    exit 1
}

# ---- Tauri (foreground) ----
Push-Location (Join-Path $Root 'apps\desktop')
try {
    & pnpm tauri dev
} finally {
    Pop-Location
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
}