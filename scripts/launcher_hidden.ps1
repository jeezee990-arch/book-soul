<#
.SYNOPSIS
    Book Soul 静默启动器 —— 像独立软件一样双击即用。

.DESCRIPTION
    本脚本由 scripts\launcher.vbs 通过 wscript.exe 以隐藏窗口调用，
    用户全程看不到控制台窗口，只看到 Book Soul 应用窗口。

    启动策略（按优先级）：
      1. **独立版**（推荐）：已打包好的 Book Soul.exe —— 这才是真正的"独立软件"，
         不需要 Python / Node / Rust，双击即用。
      2. **开发版**：没有独立版时退回 `pnpm tauri dev`（需要开发环境）。

    独立版的数据目录是 exe 同级的 data/ —— 整个文件夹拷走就是完整迁移。

.NOTES
    PowerShell 5.1 读 UTF-8 无 BOM 文件会按 ANSI 解码，导致中文注释乱码甚至
    解析失败。本文件注释保持 ASCII（英文），避免这个坑。
#>

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $PSCommandPath
$RepoRoot  = (Resolve-Path (Join-Path $ScriptDir '..')).Path
$LogFile   = Join-Path $env:TEMP 'book-soul-launcher.log'

function Write-Log([string]$Message) {
    $ts = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    Add-Content -Path $LogFile -Value "[$ts] $Message" -Encoding UTF8
}

# ===== 找独立版 exe =====
function Get-StandaloneExe {
    <#
      按优先级返回打包好的 exe 路径；找不到返回 $null。

      候选位置：
        1. dist\Book Soul\*.exe        —— build_standalone.ps1 收集好的发行目录（最正规）
        2. src-tauri\target\release\*.exe —— cargo/tauri 直接构建产物
    #>
    $candidates = @(
        (Join-Path $RepoRoot 'dist\Book Soul'),
        (Join-Path $RepoRoot 'apps\desktop\src-tauri\target\release')
    )
    foreach ($dir in $candidates) {
        if (-not (Test-Path $dir)) { continue }
        # 排除 sidecar 本体（book-soul-server*.exe），它不是应用入口
        $hit = Get-ChildItem -Path $dir -Filter '*.exe' -File -ErrorAction SilentlyContinue |
               Where-Object { $_.Name -notlike 'book-soul-server*' } |
               Sort-Object Length -Descending |
               Select-Object -First 1
        if ($hit) { return $hit.FullName }
    }
    return $null
}

Write-Log "launcher started (repo=$RepoRoot)"

# ===== 路径 1：独立版 =====
$standalone = Get-StandaloneExe
if ($standalone) {
    Write-Log " launching standalone: $standalone"
    try {
        Start-Process -FilePath $standalone -WorkingDirectory (Split-Path -Parent $standalone) | Out-Null
        exit 0
    } catch {
        Write-Log " standalone launch failed: $_"
    }
}

# ===== 路径 2：开发版 =====
Write-Log " no standalone build found, falling back to dev mode"

$venvPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$nodeModules = Join-Path $RepoRoot 'apps\desktop\node_modules'
if (-not (Test-Path $venvPython)) {
    Write-Log " MISSING: .venv (run: cd server; uv sync)"
}
if (-not (Test-Path $nodeModules)) {
    Write-Log " MISSING: node_modules (run: cd apps\desktop; pnpm install)"
}

$cargoBin = Join-Path $env:USERPROFILE '.cargo\bin'
if (Test-Path (Join-Path $cargoBin 'cargo.exe')) {
    $env:PATH = "$cargoBin;$env:PATH"
} else {
    Write-Log " MISSING: cargo (install Rust from https://rustup.rs/)"
}

$devLog = Join-Path $env:TEMP 'book-soul-dev.out.log'
$devErr = Join-Path $env:TEMP 'book-soul-dev.err.log'

Push-Location (Join-Path $RepoRoot 'apps\desktop')
try {
    # Tauri 的 beforeDevCommand 会先拉起 Vite；Rust 侧再自动拉起 Python 后端。
    & pnpm tauri dev *>> $devLog
} catch {
    Write-Log " dev mode failed: $_"
} finally {
    Pop-Location
}
Write-Log " dev mode exited"
