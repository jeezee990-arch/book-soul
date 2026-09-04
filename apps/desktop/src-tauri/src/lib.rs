//! Book Soul Tauri 库入口。
//!
//! Phase 0 模块 0.7：只暴露一个 `ping` 命令验证通联。
//! 后续模块会加入：调用 Python 后端的 HTTP 客户端、文件系统操作等。
//!
//! Phase 3.4 增强：Tauri 启动时**自动 spawn Python 后端子进程**，
//! 不再需要用户手动跑 `dev.ps1`。退出时自动 kill。

use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;
use tauri::Manager;

/// 健康检查命令（被前端 invoke("ping") 调用）。
#[tauri::command]
fn ping() -> String {
    "pong from Book Soul desktop".to_string()
}

/// 通用 HTTP 代理命令（被前端 invoke("api_request") 调用）。
///
/// 任何方法 × 任意路径 → 透传到 Python FastAPI 后端。
/// 避免每个实体在 Rust 端写一个 command。
#[tauri::command]
async fn api_request(
    method: String,
    path: String,
    body: Option<Value>,
) -> Result<Value, String> {
    let base = std::env::var("BOOK_SOUL_BACKEND_URL")
        .unwrap_or_else(|_| "http://127.0.0.1:8765".to_string());
    let url = format!("{}{}", base.trim_end_matches('/'), path);

    let client = reqwest::Client::builder()
        // Phase 3.3: 30s 太短，generate-plot 串行 3 次 LLM 容易超时
        // （minimax 海外 5-15s/次）。提到 120s 覆盖最坏情况。
        .timeout(std::time::Duration::from_secs(120))
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
///
/// 端口和地址从环境变量读取：
/// - BOOK_SOUL_BACKEND_URL（默认 http://127.0.0.1:8765）
#[tauri::command]
async fn test_llm(
    prompt: Option<String>,
    provider: Option<String>,
    max_tokens: Option<u32>,
    system: Option<String>,
) -> Result<LlmTestResponse, String> {
    let base = std::env::var("BOOK_SOUL_BACKEND_URL")
        .unwrap_or_else(|_| "http://127.0.0.1:8765".to_string());
    let url = format!("{}/llm/test", base.trim_end_matches('/'));

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

// ===== Phase 3.4：Tauri 自动启动 Python 后端 =====

/// 找 repo root：向上找包含 `.venv/` 和 `server/` 的目录。
fn find_repo_root() -> Option<PathBuf> {
    // 起点：CARGO_MANIFEST_DIR = apps/desktop/src-tauri
    // 目标：repo root（含 .venv 和 server）
    let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let candidate = manifest.parent()?.parent()?.parent()?;
    if candidate.join(".venv").is_dir() && candidate.join("server").is_dir() {
        Some(candidate.to_path_buf())
    } else {
        None
    }
}

/// 检查 127.0.0.1:8765 是否已经被占（说明已经有后端在跑）。
fn is_port_in_use() -> bool {
    std::net::TcpStream::connect_timeout(
        &"127.0.0.1:8765".parse().unwrap(),
        Duration::from_millis(300),
    )
    .is_ok()
}

/// spawn Python 后端进程（如果端口没被占）。
fn spawn_backend() -> Option<Child> {
    let repo_root = match find_repo_root() {
        Some(p) => p,
        None => {
            eprintln!("[book-soul] cannot find repo root; skip auto backend");
            return None;
        }
    };
    let python = repo_root.join(".venv").join("Scripts").join("python.exe");
    if !python.is_file() {
        eprintln!("[book-soul] python not found at {}; skip", python.display());
        return None;
    }
    let server_dir = repo_root.join("server");
    let data_dir = repo_root.join("data").join("dev");
    std::fs::create_dir_all(&data_dir).ok();

    // 输出日志到 data/dev/logs/backend-spawned.log（避免 console 刷屏）
    let log_path = data_dir.join("backend-spawned.log");
    let log_file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)
        .ok();

    let mut cmd = Command::new(&python);
    cmd.arg("-m").arg("src.main")
        .current_dir(&server_dir)
        .env("BOOK_SOUL_DATA_DIR", &data_dir)
        .stdin(Stdio::null());

    if let Some(f) = log_file {
        cmd.stdout(Stdio::from(f));
        // stderr 也用同一个文件
        let err_file = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&log_path)
            .ok();
        if let Some(f) = err_file {
            cmd.stderr(Stdio::from(f));
        } else {
            cmd.stderr(Stdio::null());
        }
    } else {
        cmd.stdout(Stdio::null()).stderr(Stdio::null());
    }

    eprintln!(
        "[book-soul] spawning backend: python={} cwd={} data={}",
        python.display(),
        server_dir.display(),
        data_dir.display(),
    );
    match cmd.spawn() {
        Ok(child) => {
            eprintln!("[book-soul] backend spawned (pid={:?})", child.id());
            Some(child)
        }
        Err(e) => {
            eprintln!("[book-soul] spawn backend failed: {e}");
            None
        }
    }
}

/// Tauri-managed 状态：后端进程句柄（用于退出时 kill）。
struct BackendProcess(Mutex<Option<Child>>);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // 启动前：如果 8765 已被占（dev.ps1 在跑），不起新的；否则 spawn
    let pre_existing = is_port_in_use();
    let child = if pre_existing {
        eprintln!("[book-soul] backend port already in use; skip spawn");
        None
    } else {
        spawn_backend()
    };

    tauri::Builder::default()
        .setup(move |app| {
            // 后端进程句柄存到 app state（让 on_window_event 能取到）
            app.manage(BackendProcess(Mutex::new(child)));
            Ok(())
        })
        .on_window_event(|window, event| {
            // 主窗口关闭时 kill Python 子进程
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                if let Ok(mut guard) = window.state::<BackendProcess>().0.lock() {
                    if let Some(mut child) = guard.take() {
                        eprintln!(
                            "[book-soul] killing backend (pid={:?})",
                            child.id()
                        );
                        let _ = child.kill();
                        let _ = child.wait();
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![ping, test_llm, api_request])
        .run(tauri::generate_context!())
        .expect("error while running Book Soul desktop application");
}
