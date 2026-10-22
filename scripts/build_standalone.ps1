<#
.SYNOPSIS
    一键构建 Book Soul 独立版（可双击即用的便携目录）。

.DESCRIPTION
    产出物：``<repo>\dist\Book Soul\``，里面是：
        Book Soul.exe        —— 应用入口（双击即用，无控制台）
        book-soul-server.exe —— Python 后端 sidecar（由应用自动拉起）
        data\                —— 运行时数据（数据库、密钥、日志）
        README.txt           —— 给用户看的一句话说明

    整个文件夹拷到任何地方都能跑（便携模式）—— 这是"像独立软件一样"的关键：
    不需要装 Python / Node / Rust，不需要配环境变量，不写注册表。

    流程：
        1. 环境自检（uv / pnpm / cargo / rustc）
        2. pnpm tauri build
             ├─ beforeBuildCommand → scripts\build_sidecar.ps1（PyInstaller 打后端）
             ├─ pnpm build（前端）
             ├─ cargo build --release（Tauri 壳）
             └─ tauri bundler（打包）
        3. 收集产物到 dist\Book Soul\

    耗时参考：首次约 5-8 分钟（Rust release 编译最慢），之后约 1-2 分钟。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\build_standalone.ps1
#>

$ErrorActionPreference = 'Stop'

$repoRoot   = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$desktopDir = Join-Path $repoRoot 'apps\desktop'
$tauriDir   = Join-Path $desktopDir 'src-tauri'
$releaseDir = Join-Path $tauriDir 'target\release'
$bundleApp  = Join-Path $releaseDir 'bundle\app'
$distDir    = Join-Path $repoRoot 'dist\Book Soul'

# ===== 1. 环境自检 =====
$missing = $false
foreach ($tool in @('uv', 'pnpm', 'cargo', 'rustc')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Host "[X] $tool not found in PATH" -ForegroundColor Red
        $missing = $true
    }
}
$cargoBin = Join-Path $env:USERPROFILE '.cargo\bin'
if ((-not (Get-Command cargo -ErrorAction SilentlyContinue)) -and (Test-Path (Join-Path $cargoBin 'cargo.exe'))) {
    $env:PATH = "$cargoBin;$env:PATH"
}
if ($missing) {
    Write-Host "Fix: install the missing tools, then re-run." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Magenta
Write-Host "  Book Soul - Build Standalone" -ForegroundColor Magenta
Write-Host "  Repo: $repoRoot" -ForegroundColor DarkGray
Write-Host "============================================" -ForegroundColor Magenta
Write-Host ""

# ===== 2. 构建 =====
Push-Location $desktopDir
try {
    Write-Host "[1/2] pnpm tauri build (this takes a few minutes)..." -ForegroundColor Cyan
    & pnpm tauri build
    if ($LASTEXITCODE -ne 0) {
        throw "tauri build failed with exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

# ===== 3. 收集产物 =====
Write-Host ""
Write-Host "[2/2] Collecting artifacts..." -ForegroundColor Cyan

# 清掉旧产物，避免残留上一版的文件
if (Test-Path -LiteralPath $distDir) {
    Remove-Item -LiteralPath $distDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $distDir | Out-Null

# 候选来源（按优先级）：
#   1. cargo 产物目录 target\release\ —— **cargo 每次都会重写这里**，
#      sidecar（book-soul-server.exe）也由 tauri-build 的 copy_binaries 放在同目录。
#   2. tauri bundler 的 app 目标 target\release\bundle\app\ —— 兜底。
#
# ⚠️ 为什么不用 bundle\app 当首选：实测它**不会随每次构建刷新**
#    （bundle/app 里的 exe 停留在旧时间戳，而 target/release 里的是新的）。
#    拿它当来源会打出一个"改了代码但行为没变"的包，最难排查。
$candidates = @(
    $releaseDir,
    (Join-Path $releaseDir 'bundle\app')
)
$sourceDir = $null
foreach ($cand in $candidates) {
    Write-Host "  probing: $cand"
    if (-not (Test-Path -LiteralPath $cand)) {
        Write-Host "    (not found)"
        continue
    }
    $exes = @(Get-ChildItem -LiteralPath $cand -Filter '*.exe' -File -ErrorAction SilentlyContinue)
    if ($exes.Count -gt 0) {
        $sourceDir = $cand
        Write-Host "    -> $($exes.Count) exe found"
        break
    }
    Write-Host "    (no exe inside)"
}
if (-not $sourceDir) {
    Write-Host "  releaseDir = $releaseDir"
    Write-Host "  bundleApp  = $(Join-Path $releaseDir 'bundle\app')"
    throw "no build output found under: $releaseDir"
}

$copied = 0
Get-ChildItem -LiteralPath $sourceDir -Filter '*.exe' -File | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $distDir $_.Name) -Force
    $copied++
}
if ($copied -eq 0) {
    throw "no executable produced in $sourceDir"
}

# ===== 新鲜度自检 =====
# 打出一个"比源码还旧"的包，比打包失败更难查。这里显式比对一下。
$newestSource = Get-ChildItem -LiteralPath (Join-Path $desktopDir 'src') -Recurse -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
$newestRust = Get-ChildItem -LiteralPath (Join-Path $tauriDir 'src') -Recurse -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
$oldestExe = Get-ChildItem -LiteralPath $distDir -Filter '*.exe' -File |
    Sort-Object LastWriteTime | Select-Object -First 1
if ($newestSource -and $oldestExe -and $oldestExe.LastWriteTime -lt $newestSource.LastWriteTime) {
    Write-Host "  [!] WARNING: 打出来的 exe 比前端源码还旧 —— 打包结果不可信" -ForegroundColor Yellow
    Write-Host "      exe : $($oldestExe.LastWriteTime)" -ForegroundColor DarkGray
    Write-Host "      src : $($newestSource.LastWriteTime)  $($newestSource.Name)" -ForegroundColor DarkGray
}
if ($newestRust -and $oldestExe -and $oldestExe.LastWriteTime -lt $newestRust.LastWriteTime) {
    Write-Host "  [!] WARNING: 打出来的 exe 比 Rust 源码还旧 —— 打包结果不可信" -ForegroundColor Yellow
    Write-Host "      exe : $($oldestExe.LastWriteTime)" -ForegroundColor DarkGray
    Write-Host "      src : $($newestRust.LastWriteTime)  $($newestRust.Name)" -ForegroundColor DarkGray
}

# 主程序改名成 "Book Soul.exe"（cargo 默认叫 book-soul-desktop.exe，
# 改名后用户看到的、快捷方式指向的才是产品名）
$mainExe = Get-ChildItem -LiteralPath $distDir -Filter '*.exe' -File |
    Where-Object { $_.Name -notlike 'book-soul-server*' } |
    Sort-Object Length -Descending |
    Select-Object -First 1
if ($mainExe -and $mainExe.Name -ne 'Book Soul.exe') {
    Rename-Item -LiteralPath $mainExe.FullName -NewName 'Book Soul.exe' -Force
    Write-Host "  renamed main exe -> 'Book Soul.exe'"
}

# 数据目录（便携模式下应用会自动在这里建库 / 存密钥 / 写日志）
New-Item -ItemType Directory -Force -Path (Join-Path $distDir 'data') | Out-Null

# 给用户的一句话说明
$readme = @"
Book Soul - AI 辅助小说写作
================================

怎么用：
  1. 双击 Book Soul.exe（或本目录里的 .exe）
  2. 窗口打开就能用了，不用开终端、不用装任何东西

数据在哪：
  本目录的 data\ 文件夹里（数据库、API Key、日志）
  整个文件夹拷到别的地方也能用 —— 这就是"便携模式"

API Key 怎么配（三种，按优先级）：
  1. 环境变量（BOOK_SOUL_API_KEY / 对应 provider 的变量名）—— 优先级最高
  2. 在软件"设置"页里填 —— 用 Windows DPAPI 加密后存在 data\secrets\，明文不落盘
  3. 系统凭据管理器

出问题了看日志：
  data\logs\desktop.log   —— 桌面端（启动失败原因在这里）
  data\logs\server.log    —— 后端业务日志
  data\logs\backend.log   —— 后端进程原始输出
"@
$readme | Out-File -FilePath (Join-Path $distDir 'README.txt') -Encoding UTF8

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Standalone build ready" -ForegroundColor Green
Write-Host "  Location: $distDir" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Get-ChildItem $distDir | ForEach-Object {
    $size = if ($_.PSIsContainer) { '<dir>' } else { "{0,6} MB" -f [math]::Round($_.Length / 1MB, 1) }
    Write-Host ("  {0,-24} {1}" -f $_.Name, $size)
}
Write-Host ""
Write-Host "Next: scripts\install_shortcut.ps1   (创建桌面快捷方式)"
Write-Host ""
