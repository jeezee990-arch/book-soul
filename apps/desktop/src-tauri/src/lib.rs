//! Book Soul Tauri 库入口。
//!
//! 桌面化（P2 目标：像传统独立应用一样双击即用）
//! ---------------------------------------------------------------------------
//! - **自动拉起 Python 后端**：dev 用仓库源码，release 用 PyInstaller 打的 sidecar exe
//! - **随机空闲端口**：避免多开冲突 / 旧进程残留（不再死绑 8765）
//! - **就绪握手**：Rust 侧等 `/ping` 通过，前端再开始拉数据（消除"点了没反应"）
//! - **便携数据目录**：exe 同级 `data/`（整个文件夹拷走就是完整迁移）
//! - **窗口关闭时 kill 后端子进程**
//!
//! 流式请求**不经过 Rust**：前端直连后端 HTTP（`invoke` 是一次性调用，
//! 做不了流式转发）。Rust 只负责普通 API 代理 + 端口/路径下发。

use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::net::{TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;
use tauri::path::BaseDirectory;
use tauri::Manager;

/// 默认端口（仅在"复用已有 dev 后端"时使用）
const DEFAULT_PORT: u16 = 8765;
/// sidecar 可执行文件名（不带平台后缀）
const SIDECAR_NAME: &str = "book-soul-server";
/// 后端就绪等待上限
const BACKEND_READY_TIMEOUT_SECS: u64 = 30;
/// 探测端口时的连接超时
const PROBE_TIMEOUT: Duration = Duration::from_millis(300);

/// 后端运行时状态（由 Tauri 管理，前端通过 command 读取）
struct BackendState {
    /// 后端根地址，如 http://127.0.0.1:54321
    url: String,
    /// 数据目录（便携模式：exe 同级 data/）
    data_dir: PathBuf,
}

/// 健康检查命令（被前端 invoke("ping") 调用）。
#[tauri::command]
fn ping() -> String {
    "pong from Book Soul desktop".to_string()
}

/// 取后端地址（前端流式请求直连用）。
#[tauri::command]
fn get_backend_url(state: tauri::State<'_, BackendState>) -> String {
    state.url.clone()
}

/// 取数据目录（前端展示 / 导出用）。
#[tauri::command]
fn get_data_dir(state: tauri::State<'_, BackendState>) -> String {
    state.data_dir.to_string_lossy().to_string()
}

/// 等待后端就绪（前端启动时调用，避免首屏就 503）。
///
/// 返回 true = 后端已就绪；false = 超时（前端应显示"启动中/失败"而不是白屏）。
///
/// 注意：Tauri 2 的 **async command 带 `State` 引用时必须返回 `Result`**，
/// 否则编译不过（``AsyncCommandMustReturnResult``）。
#[tauri::command]
async fn backend_ready(
    state: tauri::State<'_, BackendState>,
    timeout_ms: Option<u64>,
) -> Result<bool, String> {
    let timeout = Duration::from_millis(timeout_ms.unwrap_or(BACKEND_READY_TIMEOUT_SECS * 1000));
    let client = match reqwest::Client::builder()
        .timeout(Duration::from_secs(3))
        .build()
    {
        Ok(c) => c,
        Err(e) => return Err(format!("http client build failed: {e}")),
    };
    let deadline = std::time::Instant::now() + timeout;
    loop {
        if let Ok(resp) = client.get(format!("{}/ping", state.url)).send().await {
            if resp.status().is_success() {
                return Ok(true);
            }
        }
        if std::time::Instant::now() >= deadline {
            return Ok(false);
        }
        tokio::time::sleep(Duration::from_millis(150)).await;
    }
}

/// 通用 HTTP 代理命令（被前端 invoke("api_request") 调用）。
///
/// 任何方法 × 任意路径 → 透传到 Python FastAPI 后端。
/// 避免每个实体在 Rust 端写一个 command。
#[tauri::command]
async fn api_request(
    state: tauri::State<'_, BackendState>,
    method: String,
    path: String,
    body: Option<Value>,
) -> Result<Value, String> {
    let url = format!("{}{}", state.url.trim_end_matches('/'), path);

    let client = reqwest::Client::builder()
        // 大纲生成（单次 LLM 长调用）实测 mimo 需 ~110s，120s 余量不足；
        // 180s 覆盖最坏情况（剧情生成已并行化，约 40s）。
        .timeout(std::time::Duration::from_secs(180))
        .build()
        .map_err(|e| format!("client: {e}"))?;

    let mut req = match method.to_uppercase().as_str() {
        "GET" => client.get(&url),
        "POST" => client.post(&url),
        "PUT" => client.put(&url),
        "PATCH" => client.patch(&url),
        "DELETE" => client.delete(&url),
        m => return Err(format!("unsupported method: {m}")),
    };
    if let Some(b) = body {
        req = req.json(&b);
    }

    let resp = req.send().await.map_err(|e| format!("network: {e}"))?;
    let status = resp.status();
    if !status.is_success() {
        let text = resp.text().await.unwrap_or_default();
        return Err(format!("HTTP {}: {}", status, text));
    }
    if status == reqwest::StatusCode::NO_CONTENT {
        return Ok(Value::Null);
    }
    resp.json().await.map_err(|e| format!("parse: {e}"))
}

#[derive(Debug, Serialize, Deserialize)]
struct LlmTestRequest {
    #[serde(default)]
    prompt: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    provider: Option<String>,
    #[serde(default = "default_max_tokens")]
    max_tokens: u32,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    system: Option<String>,
}

fn default_max_tokens() -> u32 {
    200
}

#[derive(Debug, Serialize, Deserialize)]
struct LlmTestResponse {
    provider: String,
    model: String,
    content: String,
    #[serde(default)]
    prompt_tokens: u32,
    #[serde(default)]
    completion_tokens: u32,
    #[serde(default)]
    total_tokens: u32,
}

/// LLM 测试命令：调 Python `/llm/test` 端点拿到真实回复。
#[tauri::command]
async fn test_llm(
    state: tauri::State<'_, BackendState>,
    prompt: Option<String>,
    provider: Option<String>,
    max_tokens: Option<u32>,
    system: Option<String>,
) -> Result<LlmTestResponse, String> {
    let url = format!("{}/llm/test", state.url.trim_end_matches('/'));

    let req = LlmTestRequest {
        prompt: prompt.unwrap_or_else(|| "用一句话介绍你自己".to_string()),
        provider,
        max_tokens: max_tokens.unwrap_or(200),
        system,
    };

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(60))
        .build()
        .map_err(|e| format!("reqwest client: {e}"))?;

    let resp = client
        .post(&url)
        .json(&req)
        .send()
        .await
        .map_err(|e| format!("network error: {e}"))?;

    let status = resp.status();
    if !status.is_success() {
        let text = resp.text().await.unwrap_or_default();
        return Err(format!("HTTP {}: {}", status, text));
    }

    let body: LlmTestResponse = resp
        .json()
        .await
        .map_err(|e| format!("parse response: {e}"))?;

    Ok(body)
}

// =========================================================================
// 端口 / 数据目录 / 后端进程
// =========================================================================

/// 找一个空闲端口（bind :0 让 OS 分配）。
fn pick_free_port() -> u16 {
    TcpListener::bind(("127.0.0.1", 0))
        .and_then(|l| l.local_addr())
        .map(|a| a.port())
        .unwrap_or(DEFAULT_PORT)
}

/// 找 repo root：向上找包含 `.venv/` 和 `server/` 的目录。
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
/// - **dev**：`<repo>/data/dev`（和现在的行为一致）
/// - **release（便携模式）**：`<exe 同级>/data` —— 整个文件夹拷走就是完整迁移
/// - 兜底：系统 app data 目录
fn resolve_data_dir(app: &tauri::AppHandle) -> PathBuf {
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
        .unwrap_or_else(|_| PathBuf::from("data"))
}

/// 解析 sidecar 可执行文件路径（release 模式）。
///
/// `bundle.externalBin` 里的文件在打包后位于**资源目录**，文件名去掉平台后缀。
fn resolve_sidecar_path(app: &tauri::AppHandle) -> Option<PathBuf> {
    let p = app
        .path()
        .resolve(SIDECAR_NAME, BaseDirectory::Resource)
        .ok()?;
    if p.is_file() {
        return Some(p);
    }
    // 兜底：exe 同级（部分打包配置会这样放）
    let exe = std::env::current_exe().ok()?;
    let dir = exe.parent()?;
    for name in [
        format!("{SIDECAR_NAME}{}", std::env::consts::EXE_SUFFIX),
        SIDECAR_NAME.to_string(),
    ] {
        let cand = dir.join(name);
        if cand.is_file() {
            return Some(cand);
        }
    }
    None
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
) -> Option<Command> {
    let mut cmd: Command;

    if cfg!(debug_assertions) {
        // dev：跑仓库源码
        let root = find_repo_root()?;
        let python = root.join(".venv").join("Scripts").join("python.exe");
        if !python.is_file() {
            eprintln!("[book-soul] python not found at {}; skip", python.display());
            return None;
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

    Some(cmd)
}

/// Tauri-managed 状态：后端进程句柄（用于退出时 kill）。
struct BackendProcess(Mutex<Option<Child>>);

/// 启动后端并等待就绪。
///
/// :return: (url, child)
fn start_backend(app: &tauri::AppHandle) -> (String, Option<Child>) {
    let data_dir = resolve_data_dir(app);
    std::fs::create_dir_all(&data_dir).ok();

    // dev 场景：如果默认端口已经有**本项目**的后端在跑（dev.ps1 起的），直接复用，不重复起
    if cfg!(debug_assertions) {
        let dev_url = format!("http://127.0.0.1:{DEFAULT_PORT}");
        if is_url_alive(&dev_url) {
            eprintln!("[book-soul] reuse existing dev backend on {DEFAULT_PORT}");
            return (dev_url, None);
        }
    }

    let port = pick_free_port();
    let url = format!("http://127.0.0.1:{port}");
    eprintln!("[book-soul] starting backend on {url} (data={})", data_dir.display());

    let mut cmd = match build_backend_command(app, port, &data_dir) {
        Some(c) => c,
        None => {
            eprintln!("[book-soul] cannot build backend command; skip spawn");
            return (url, None);
        }
    };

    match cmd.spawn() {
        Ok(child) => {
            eprintln!("[book-soul] backend spawned (pid={:?})", child.id());
            (url, Some(child))
        }
        Err(e) => {
            eprintln!("[book-soul] spawn backend failed: {e}");
            (url, None)
        }
    }
}

/// 极简 HTTP 存活探测：发一个 `GET /ping` 看是否返回 200。
///
/// 用 std::net 手写而不用 reqwest —— 这里要的是**同步**探活，
/// 而 reqwest 是异步的（且 blocking feature 没开）。
fn is_url_alive(url: &str) -> bool {
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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(move |app| {
            let handle = app.handle().clone();
            let (url, child) = start_backend(&handle);

            // ⚠️ 这里**不阻塞**等就绪 —— 阻塞会让窗口迟迟不出现，用户以为没启动。
            // 由前端调 `backend_ready` 命令做握手，期间显示"正在启动引擎…"。
            eprintln!("[book-soul] backend starting at {url}");

            let data_dir = resolve_data_dir(&handle);
            app.manage(BackendState { url, data_dir });
            // 后端进程句柄存到 app state（让 on_window_event 能取到）
            app.manage(BackendProcess(Mutex::new(child)));
            Ok(())
        })
        .on_window_event(|window, event| {
            // 主窗口关闭时 kill Python 子进程
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                if let Ok(mut guard) = window.state::<BackendProcess>().0.lock() {
                    if let Some(mut child) = guard.take() {
                        eprintln!("[book-soul] killing backend (pid={:?})", child.id());
                        let _ = child.kill();
                        let _ = child.wait();
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            ping,
            test_llm,
            api_request,
            get_backend_url,
            get_data_dir,
            backend_ready
        ])
        .run(tauri::generate_context!())
        .expect("error while running Book Soul desktop application");
}
