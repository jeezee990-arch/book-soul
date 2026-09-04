# Start Book Soul Python backend (standalone, for pnpm tauri dev beforeDevCommand).
#
# Behavior:
#   - Check 127.0.0.1:8765; if taken, skip (auto-spawn already done by Tauri/Rust).
#   - Else: kill stale Python on 8765, start new Python -m src.main.
#   - Wait for /ping 200 (max 30s).
#   - Process keeps running in background (does not block dev session).
#   - exit 0 / 1.
#
# NOTE: Avoid non-ASCII in this file. PowerShell 5.1 reads UTF-8 without BOM
# as ANSI, so CJK comments break the parser. Keep comments ASCII.

$ErrorActionPreference = 'Stop'

$ScriptDir  = Split-Path -Parent $PSCommandPath
$RepoRoot   = Split-Path -Parent $ScriptDir
$ServerDir  = Join-Path $RepoRoot 'server'
$PythonExe  = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$BackendUrl = 'http://127.0.0.1:8765'
$LogDir     = $env:TEMP

if (-not (Test-Path $PythonExe)) {
    Write-Error "[X] Python not found: $PythonExe"
}
if (-not (Test-Path $ServerDir)) {
    Write-Error "[X] server dir not found: $ServerDir"
}

$DevDataDir = Join-Path $RepoRoot 'data\dev'
if (-not (Test-Path $DevDataDir)) {
    New-Item -ItemType Directory -Path $DevDataDir | Out-Null
}
$env:BOOK_SOUL_DATA_DIR = $DevDataDir

# Check 8765
try {
    $resp = Invoke-WebRequest -Uri "$BackendUrl/ping" -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop
    if ($resp.StatusCode -eq 200) {
        Write-Host "[backend] already running on $BackendUrl"
        exit 0
    }
} catch { }

# Kill stale Python on 8765
$PortOwners = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
foreach ($Conn in $PortOwners) {
    $OldProc = Get-Process -Id $Conn.OwningProcess -ErrorAction SilentlyContinue
    if ($OldProc -and $OldProc.ProcessName -eq 'python') {
        Write-Host "       Killing stale Python PID $($OldProc.Id) on port 8765"
        Stop-Process -Id $OldProc.Id -Force
    }
}
Start-Sleep -Seconds 1

# Start Python (cmd.exe /c to ensure env propagates)
$PythonLog = Join-Path $LogDir 'book-soul-backend.out.log'
$PythonErr = Join-Path $LogDir 'book-soul-backend.err.log'
$CmdArgs = '/c', "set `"BOOK_SOUL_DATA_DIR=$DevDataDir`" && `"$PythonExe`" -m src.main"

Write-Host "[backend] starting: $PythonExe"
$PythonProc = Start-Process `
    -FilePath 'cmd.exe' `
    -ArgumentList $CmdArgs `
    -WorkingDirectory $ServerDir `
    -PassThru `
    -WindowStyle Hidden `
    -RedirectStandardOutput $PythonLog `
    -RedirectStandardError $PythonErr
Write-Host "       Python PID: $($PythonProc.Id)"

# Wait /ping
$MaxWaitSec = 30
$Waited = 0
$Ready = $false
while ($Waited -lt $MaxWaitSec) {
    Start-Sleep -Seconds 1
    $Waited++
    try {
        $r = Invoke-WebRequest -Uri "$BackendUrl/ping" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($r.StatusCode -eq 200) {
            Write-Host "       Ready in ${Waited}s"
            $Ready = $true
            break
        }
    } catch { }
}

if (-not $Ready) {
    Write-Error "[X] Backend not ready in ${MaxWaitSec}s. Check log: $PythonErr"
}
exit 0
