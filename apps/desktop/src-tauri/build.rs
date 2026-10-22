//! Tauri 构建脚本。
//!
//! 除了标准的 `tauri_build::build()`，这里额外做一件事：
//! **保证 `externalBin` 声明的 sidecar 文件存在**。
//!
//! 背景
//! ----
//! `tauri.conf.json` 里配了 `externalBin: ["binaries/book-soul-server"]`，
//! Tauri 在构建时会校验
//! `binaries/book-soul-server-<target-triple>[.exe]` 是否存在，**不存在就直接
//! 报错退出**。这会导致：
//!   - 本地跑 `cargo check` 也要先花 2 分钟打 sidecar
//!   - CI 的 `cargo check` 步骤直接挂
//!
//! 处理
//! -----
//! sidecar 不存在时，放一个**占位文件**让校验通过，并打印醒目警告。
//! 真正的打包流程（`pnpm tauri build`）会先跑 `beforeBuildCommand`
//! → `scripts/build_sidecar.ps1`，它会生成**真实**的 exe，占位文件不会被使用。
//! 若 sidecar 构建失败，`beforeBuildCommand` 里的 `&&` 会让整个构建中止，
//! 不会出现"把占位文件打进安装包"的情况。

use std::path::PathBuf;

fn main() {
    ensure_sidecar_placeholder();
    tauri_build::build()
}

/// sidecar 的目标三元组（与 Tauri 期望的命名一致）
fn target_triple() -> String {
    // 由 tauri-build 注入；拿不到时退回常见值
    std::env::var("TAURI_ENV_TARGET_TRIPLE").unwrap_or_else(|_| {
        let arch = std::env::var("CARGO_CFG_TARGET_ARCH").unwrap_or_default();
        let os = std::env::var("CARGO_CFG_TARGET_OS").unwrap_or_default();
        let env = std::env::var("CARGO_CFG_TARGET_ENV").unwrap_or_default();
        match (arch.as_str(), os.as_str(), env.as_str()) {
            ("x86_64", "windows", "msvc") => "x86_64-pc-windows-msvc".to_string(),
            ("aarch64", "windows", "msvc") => "aarch64-pc-windows-msvc".to_string(),
            ("x86_64", "windows", "gnu") => "x86_64-pc-windows-gnu".to_string(),
            ("x86_64", "linux", "gnu") => "x86_64-unknown-linux-gnu".to_string(),
            ("aarch64", "linux", "gnu") => "aarch64-unknown-linux-gnu".to_string(),
            ("aarch64", "macos", "") => "aarch64-apple-darwin".to_string(),
            ("x86_64", "macos", "") => "x86_64-apple-darwin".to_string(),
            _ => "x86_64-pc-windows-msvc".to_string(),
        }
    })
}

fn ensure_sidecar_placeholder() {
    let triple = target_triple();
    let exe_suffix = if cfg!(target_os = "windows") { ".exe" } else { "" };
    let rel = format!("binaries/book-soul-server-{triple}{exe_suffix}");

    let manifest_dir = std::env::var("CARGO_MANIFEST_DIR").unwrap_or_default();
    let path = PathBuf::from(&manifest_dir).join(&rel);

    if path.exists() {
        return;
    }

    if let Some(parent) = path.parent() {
        if std::fs::create_dir_all(parent).is_err() {
            return;
        }
    }

    // 写一个最小可执行占位（Windows PE 头让 tauri 的校验更接近真实情况）
    let mut stub: Vec<u8> = vec![0x4D, 0x5A]; // "MZ"
    stub.extend_from_slice(&[0u8; 62]);
    stub.extend_from_slice(&0x80u32.to_le_bytes()); // e_lfanew
    stub.extend_from_slice(b"PE\0\0");
    stub.extend_from_slice(&[0u8; 16]);

    if std::fs::write(&path, stub).is_ok() {
        println!(
            "cargo:warning=sidecar 占位文件已创建: {}\n\
             cargo:warning=  这只是让 cargo check 能通过。\n\
             cargo:warning=  正式打包请先跑: powershell -ExecutionPolicy Bypass -File scripts/build_sidecar.ps1",
            path.display()
        );
    }
}
