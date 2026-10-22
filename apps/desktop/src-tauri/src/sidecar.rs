//! 后端（Python sidecar）的定位、拉起与清理。
//!
//! 与 `lib.rs` 的分工
//! ------------------
//! - `lib.rs`：Tauri command、窗口事件、应用装配
//! - 本模块：纯逻辑 —— 找端口、找数据目录、找 sidecar 可执行文件、拼子进程命令
//!
//! 为什么要拆出来？
//! `lib.rs` 原本 459 行，加上日志、错误透传、看门狗会突破 AGENTS.md 的
//! "单文件 ≤ 500 行"红线。按职责拆比按行数拆干净。

use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::time::Duration;

use tauri::Manager;

use crate::logging;

/// 默认端口（仅在"复用已有 dev 后端"时使用）。
pub const DEFAULT_PORT: u16 = 8765;

/// 后端就绪等待上限（秒）。
///
/// PyInstaller 单文件 exe 首次启动要解包，叠加 Python 解释器初始化，
/// 给到 30s 比较稳（用户看到的是"正在启动引擎…"的加载屏，不是白屏）。
pub const BACKEND_READY_TIMEOUT_SECS: u64 = 30;

/// sidecar 可执行文件名（不含平台后缀、不含 target triple）。
const SIDECAR_NAME: &str = "book-soul-server";

/// 探测端口时的连接超时。
const PROBE_TIMEOUT: Duration = Duration::from_millis(300);

/// 找一个空闲端口（bind :0 让操作系统分配）。
///
/// 桌面版不再死绑 8765 —— 多开、旧进程残留都会撞端口。
pub fn pick_free_port() -> u16 {
    std::net::TcpListener::bind(("127.0.0.1", 0))
        .and_then(|l| l.local_addr())
        .map(|a| a.port())
        .unwrap_or(DEFAULT_PORT)
}

/// 找 repo root：向上找包含 `.venv/` 和 `server/` 的目录。
///
/// 只在 debug 模式用（dev 跑仓库源码）。release 模式用不到。
fn find_repo_root() -> Option<PathBuf> {
    // 起点：CARGO_MANIFEST_DIR = apps/desktop/src-tauri
    let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let candidate = manifest.parent()?.parent()?.parent()?;
    if candidate.join(".venv").is_dir() && candidate.join("server").is_dir() {
        Some(candidate.to_path_buf())
    } else {
        None
    }
}

/// 解析数据目录。
///
/// - **dev**：`<repo>/data/dev`（与开发习惯一致）
/// - **release（便携模式）**：`<exe 同级>/data` —— 整个文件夹拷走就是完整迁移
/// - 兜底：系统 app data 目录
pub fn resolve_data_dir(app: &tauri::AppHandle) -> PathBuf {
    if cfg!(debug_assertions) {
        if let Some(root) = find_repo_root() {
            return root.join("data").join("dev");
        }
    }
    // 便携模式：exe 同级 data/
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            return dir.join("data");
        }
    }
    app.path()
        .app_data_dir()
        .unwrap_or_else(|_| {
            logging::warn("无法解析系统 app data 目录，退回到相对路径 data/");
            PathBuf::from("data")
        })
}

/// 解析 sidecar 可执行文件路径（release 模式）。
///
/// Tauri 的 `copy_binaries`（tauri-build）会把
/// `binaries/book-soul-server-<target-triple>.exe` **剥掉 target triple 后缀**
/// 复制到 cargo 的 target 目录；打包时同样会去掉三元组。
/// Windows 上"资源目录 == exe 所在目录"，所以最常见的位置就是 **exe 同级**。
///
/// 这里按可靠性从高到低依次尝试，并且**失败时给出明确原因**——
/// 静默失败会让用户只看到一个"启动失败"的白屏，没有任何线索。
pub fn resolve_sidecar_path(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    let exe_file = format!("{SIDECAR_NAME}{}", std::env::consts::EXE_SUFFIX);
    let mut candidates: Vec<PathBuf> = Vec::new();

    // 1) exe 同级目录 —— cargo build 产物 + Windows 打包形态都命中这里
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            candidates.push(dir.join(&exe_file));
        }
    }

    // 2) 资源目录 —— macOS / Linux 打包形态
    if let Ok(dir) = app.path().resource_dir() {
        candidates.push(dir.join(&exe_file));
        candidates.push(dir.join(SIDECAR_NAME));
    }

    // 3) exe 的上两级（macOS 的 Contents/MacOS、Contents/Resources）
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent().and_then(|p| p.parent()) {
            candidates.push(parent.join(&exe_file));
            candidates.push(parent.join("Resources").join(&exe_file));
            candidates.push(parent.join("MacOS").join(&exe_file));
        }
    }

    for cand in &candidates {
        if cand.is_file() {
            return Ok(cand.clone());
        }
    }

    Err(format!(
        "找不到后端可执行文件 {exe_file}。已尝试：\n  {}",
        candidates
            .iter()
            .map(|p| p.display().to_string())
            .collect::<Vec<_>>()
            .join("\n  ")
    ))
}

/// 给子进程准备 stdout/stderr 日志文件。
fn prepare_log_file(data_dir: &Path) -> Option<std::fs::File> {
    let log_dir = data_dir.join("logs");
    std::fs::create_dir_all(&log_dir).ok()?;
    std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(log_dir.join("backend.log"))
        .ok()
}

/// 构造子进程命令（dev / release 两套）。
fn build_backend_command(
    app: &tauri::AppHandle,
    port: u16,
    data_dir: &Path,
) -> Result<Command, String> {
    let mut cmd: Command;

    if cfg!(debug_assertions) {
        // dev：跑仓库源码
        let root = find_repo_root().ok_or_else(|| {
            "开发模式找不到仓库根目录（需要同时存在 .venv/ 和 server/）".to_string()
        })?;
        let python = root.join(".venv").join("Scripts").join("python.exe");
        if !python.is_file() {
            return Err(format!(
                "找不到 Python 解释器：{}（先执行 cd server && uv sync）",
                python.display()
            ));
        }
        cmd = Command::new(python);
        cmd.current_dir(root.join("server"));
    } else {
        // release：跑打包好的 sidecar exe
        let sidecar = resolve_sidecar_path(app)?;
        cmd = Command::new(sidecar);
    }

    cmd.arg("--port")
        .arg(port.to_string())
        .arg("--host")
        .arg("127.0.0.1")
        // 主程序 pid：Python 侧据此判断"桌面端是否还活着"，主程序崩了就自行退出，
        // 避免留下一个占着端口的僵尸后端。
        .arg("--parent-pid")
        .arg(std::process::id().to_string())
        .env("BOOK_SOUL_DATA_DIR", data_dir)
        .env("BOOK_SOUL_HOST", "127.0.0.1")
        .env("BOOK_SOUL_PORT", port.to_string())
        .stdin(Stdio::null());

    if let Some(f) = prepare_log_file(data_dir) {
        let err_file = f.try_clone().ok();
        cmd.stdout(Stdio::from(f));
        if let Some(ef) = err_file {
            cmd.stderr(Stdio::from(ef));
        } else {
            cmd.stderr(Stdio::null());
        }
    } else {
        cmd.stdout(Stdio::null()).stderr(Stdio::null());
    }

    Ok(cmd)
}

/// 极简 HTTP 存活探测：发一个 `GET /ping` 看是否返回 200。
///
/// 用 std::net 手写而不用 reqwest —— 这里要的是**同步**探活，
/// 而 reqwest 是异步的（且 blocking feature 没开）。
pub fn is_url_alive(url: &str) -> bool {
    use std::io::{Read, Write};

    let Some(rest) = url.strip_prefix("http://") else {
        return false;
    };
    let hostport = rest.split('/').next().unwrap_or(rest);

    let mut stream = match TcpStream::connect_timeout(
        &match hostport.parse() {
            Ok(addr) => addr,
            Err(_) => return false,
        },
        PROBE_TIMEOUT,
    ) {
        Ok(s) => s,
        Err(_) => return false,
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(800)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(800)));

    let req = format!(
        "GET /ping HTTP/1.1\r\nHost: {hostport}\r\nConnection: close\r\n\r\n"
    );
    if stream.write_all(req.as_bytes()).is_err() {
        return false;
    }
    let mut buf = [0u8; 256];
    match stream.read(&mut buf) {
        Ok(n) if n > 0 => String::from_utf8_lossy(&buf[..n]).contains(" 200 "),
        _ => false,
    }
}

/// 拉起后端的结果。
pub struct BackendStart {
    /// 后端根地址（即使启动失败也有值，便于前端显示错误时带上地址）。
    pub url: String,
    /// 子进程句柄（None = 复用了已有 dev 后端，或启动失败）。
    pub child: Option<Child>,
    /// 启动失败的原因（None = 成功）。
    pub error: Option<String>,
}

/// 启动后端。
///
/// 失败**不 panic**：返回 `error`，由前端在启动屏上明确告诉用户"缺什么、怎么补"，
/// 比白屏强一百倍。
pub fn start_backend(app: &tauri::AppHandle, data_dir: &Path) -> BackendStart {
    // dev 场景：如果默认端口已经有**本项目**的后端在跑（dev.ps1 起的），直接复用，不重复起
    if cfg!(debug_assertions) {
        let dev_url = format!("http://127.0.0.1:{DEFAULT_PORT}");
        if is_url_alive(&dev_url) {
            logging::info(&format!("复用已有 dev 后端 {dev_url}"));
            return BackendStart {
                url: dev_url,
                child: None,
                error: None,
            };
        }
    }

    let port = pick_free_port();
    let url = format!("http://127.0.0.1:{port}");
    logging::info(&format!("准备启动后端 {url}（数据目录 {}）", data_dir.display()));

    let mut cmd = match build_backend_command(app, port, data_dir) {
        Ok(c) => c,
        Err(e) => {
            logging::error(&format!("后端命令构造失败：{e}"));
            return BackendStart {
                url,
                child: None,
                error: Some(e),
            };
        }
    };

    match cmd.spawn() {
        Ok(child) => {
            logging::info(&format!("后端已拉起（pid={:?}）", child.id()));
            BackendStart {
                url,
                child: Some(child),
                error: None,
            }
        }
        Err(e) => {
            let msg = format!("后端进程启动失败：{e}");
            logging::error(&msg);
            BackendStart {
                url,
                child: None,
                error: Some(msg),
            }
        }
    }
}

/// 终止后端子进程（幂等）。
pub fn kill_backend(slot: &mut Option<Child>) {
    if let Some(mut child) = slot.take() {
        logging::info(&format!("正在结束后端进程（pid={:?}）", child.id()));
        let _ = child.kill();
        let _ = child.wait();
    }
}
