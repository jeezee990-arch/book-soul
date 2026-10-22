//! 桌面端自身的日志。
//!
//! 为什么要单独写一个模块？
//! --------------------
//! release 模式下 `main.rs` 里有 `#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]`
//! —— 意思是**不弹控制台**。代价是 `eprintln!` 的输出全部进了黑洞，
//! 用户看到"启动失败"却拿不到任何线索。
//!
//! 所以桌面端把日志写到 `<data_dir>/logs/desktop.log`（追加模式）。
//! 后端 Python 的日志在同一目录下的 `backend.log`，两个文件一起看，
//! 就能还原"双击后到底发生了什么"。
//!
//! 用法
//! ----
//! ```ignore
//! logging::init(&data_dir);   // 尽早调用（setup 阶段）
//! logging::info("backend spawned");
//! ```

use std::fs::OpenOptions;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

/// 日志文件路径。`None` = 还没 init（静默降级，不影响主流程）。
static LOG_PATH: Mutex<Option<PathBuf>> = Mutex::new(None);

/// 初始化日志文件（在数据目录下建 `logs/desktop.log`）。
///
/// 失败不 panic —— 日志是辅助功能，不该因为它把整个应用搞挂。
pub fn init(data_dir: &Path) {
    let log_dir = data_dir.join("logs");
    if std::fs::create_dir_all(&log_dir).is_err() {
        return;
    }
    let path = log_dir.join("desktop.log");

    // 写 UTF-8 BOM：Windows 记事本 / 某些编辑器不认无 BOM 的 UTF-8，
    // 中文会变成乱码。加了 BOM 它们就会正确识别。
    if std::fs::metadata(&path).map(|m| m.len() == 0).unwrap_or(true) {
        if let Ok(mut f) = OpenOptions::new().create(true).append(true).open(&path) {
            let _ = f.write_all(&[0xEF, 0xBB, 0xBF]);
        }
    }

    if let Ok(mut guard) = LOG_PATH.lock() {
        *guard = Some(path);
    }
}

/// 写一行日志（自动加时间戳与级别）。
///
/// **每次都重新打开文件**（而不是长期持有句柄）：
/// 长期持有写句柄会让"应用运行期间用记事本/其他工具读日志"失败
/// （Windows 的文件共享规则：新句柄的共享模式不允许别人写 → 读也报错）。
/// 日志写入频率极低（启动期几条），多一次 open 的开销可以忽略。
pub fn log(level: &str, message: &str) {
    let path = match LOG_PATH.lock() {
        Ok(guard) => guard.clone(),
        Err(poisoned) => poisoned.into_inner().clone(),
    };
    let Some(path) = path else {
        return;
    };
    let line = format!("[{}] [{level}] {message}\n", timestamp());
    if let Ok(mut f) = OpenOptions::new().create(true).append(true).open(&path) {
        let _ = f.write_all(line.as_bytes());
    }
}

/// INFO 级别日志。
pub fn info(message: &str) {
    log("INFO", message);
}

/// WARN 级别日志。
pub fn warn(message: &str) {
    log("WARN", message);
}

/// ERROR 级别日志。
pub fn error(message: &str) {
    log("ERROR", message);
}

/// 当前本地时间戳（`YYYY-MM-DD HH:MM:SS`）。
fn timestamp() -> String {
    chrono::Local::now()
        .format("%Y-%m-%d %H:%M:%S")
        .to_string()
}
