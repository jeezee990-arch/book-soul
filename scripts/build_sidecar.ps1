<#
.SYNOPSIS
    构建 Python 后端 sidecar exe，放到 Tauri 期望的位置。

.DESCRIPTION
    Tauri 的 bundle.externalBin 约定：src-tauri/binaries/<name>-<target-triple>[.exe]
    打包时会被自动重命名并塞进安装包。

    本脚本负责：
      1. 用 PyInstaller 把 server/ 打成单文件 exe
      2. 拷贝到 src-tauri/binaries/ 并加上 target-triple 后缀

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/build_sidecar.ps1
#>
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$serverDir = Join-Path $repoRoot 'server'
$tauriDir = Join-Path $repoRoot 'apps/desktop/src-tauri'
$binDir = Join-Path $tauriDir 'binaries'

Write-Host "[sidecar] repo root: $repoRoot"

# ===== 1. 拿 target triple =====
$rustcOutput = rustc -vV 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "rustc not found. Install Rust toolchain: https://rustup.rs"
}
$triple = ($rustcOutput | Select-String '^host: ' | Select-Object -First 1)
if (-not $triple) {
    throw "cannot parse target triple from 'rustc -vV': $rustcOutput"
}
$tripleName = ($triple.ToString() -replace '^host:\s*', '').Trim()
$exeName = "book-soul-server-$tripleName.exe"
Write-Host "[sidecar] target triple: $tripleName"

# ===== 2. PyInstaller 构建 =====
if (-not (Test-Path (Join-Path $serverDir 'book_soul.spec'))) {
    throw "spec not found: server/book_soul.spec"
}

Push-Location $serverDir
try {
    Write-Host "[sidecar] running pyinstaller (this takes 1-3 min)..."
    uv run pyinstaller book_soul.spec --noconfirm --clean
    if ($LASTEXITCODE -ne 0) {
        throw "pyinstaller failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

$built = Join-Path $serverDir 'dist/book-soul-server.exe'
if (-not (Test-Path $built)) {
    throw "pyinstaller reported success but artifact not found: $built"
}

# ===== 3. 拷到 Tauri 期望位置 =====
New-Item -ItemType Directory -Force -Path $binDir | Out-Null
$dest = Join-Path $binDir $exeName
Copy-Item -Path $built -Destination $dest -Force

$sizeMb = [math]::Round((Get-Item $dest).Length / 1MB, 1)
Write-Host "[sidecar] OK -> $dest ($sizeMb MB)"
Write-Host "[sidecar] now run: pnpm tauri build"
