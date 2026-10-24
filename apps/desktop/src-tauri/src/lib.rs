//! Book Soul Tauri 库入口。
//!
//! 桌面化（P2 目标：像传统独立应用一样双击即用）
//! ---------------------------------------------------------------------------
//! - **自动拉起 Python 后端**：dev 用仓库源码，release 用 PyInstaller 打的 sidecar exe
//! - **随机空闲端口**：避免多开冲突 / 旧进程残留（不再死绑 8765）
//! - **就绪握手**：Rust 侧等 `/ping` 通过，前端再开始拉数据（消除"点了没反应"）
//! - **便携数据目录**：exe 同级 `data/`（整个文件夹拷走就是完整迁移）
//! - **窗口关闭时 kill 后端子进程**
//! - **失败可诊断**：后端拉不起来时，错误原文透传到前端启动屏 + 写进
//!   `data/logs/desktop.log`，用户不再面对白屏
//!
//! 流式请求**不经过 Rust**：前端直连后端 HTTP（`invoke` 是一次性调用，
//! 做不了流式转发）。Rust 只负责普通 API 代理 + 端口/路径下发。
//!
//! 模块划分
//! ---------------------------------------------------------------------------
//! - `logging.rs`：桌面端日志（release 没有控制台，eprintln! 会丢）
//! - `sidecar.rs`：找端口 / 找数据目录 / 找 sidecar / 拉起与终止后端

use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::path::PathBuf;
use std::process::Child;
use std::sync::Mutex;
use std::time::Duration;
use tauri::Manager;

mod logging;
mod sidecar;

/// 后端运行时状态（由 Tauri 管理，前端通过 command 读取）。
struct BackendState {
    /// 后端根地址，如 http://127.0.0.1:54321
    url: String,
    /// 数据目录（便携模式：exe 同级 data/）
    data_dir: PathBuf,
    /// 后端启动失败的原因（None = 正常）
    error: Option<String>,
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

/// 取后端启动错误（None = 正常）。
///
/// 前端启动屏据此显示"缺什么、怎么补"，而不是笼统的"启动失败"。
#[tauri::command]
fn get_backend_error(state: tauri::State<'_, BackendState>) -> Option<String> {
    state.error.clone()
}

/// 在系统文件管理器里打开数据目录。
///
/// ⚠️ 刻意**不用** shell 插件的通用 `open`：那要放开"能打开任意路径、
/// 任意程序"的权限面。这里只暴露"打开数据目录"这一个固定动作 —— 权限最小。
#[tauri::command]
fn open_data_dir(state: tauri::State<'_, BackendState>) -> Result<(), String> {
    let dir = &state.data_dir;
    if !dir.exists() {
        return Err(format!("数据目录不存在：{}", dir.display()));
    }
    let spawn_result = if cfg!(target_os = "windows") {
        std::process::Command::new("explorer.exe").arg(dir).spawn()
    } else {
        std::process::Command::new("open").arg(dir).spawn()
    };
    spawn_result.map_err(|e| format!("打开数据目录失败：{e}"))?;
    Ok(())
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
    let timeout =
        Duration::from_millis(timeout_ms.unwrap_or(sidecar::BACKEND_READY_TIMEOUT_SECS * 1000));
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

/// Tauri-managed 状态：后端进程句柄（用于退出时 kill）。
struct BackendProcess(Mutex<Option<Child>>);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .setup(move |app| {
            let handle = app.handle().clone();
            let data_dir = sidecar::resolve_data_dir(&handle);
            logging::init(&data_dir);

            let started = sidecar::start_backend(&handle, &data_dir);

            // ⚠️ 这里**不阻塞**等就绪 —— 阻塞会让窗口迟迟不出现，用户以为没启动。
            // 由前端调 `backend_ready` 命令做握手，期间显示"正在启动引擎…"。
            logging::info(&format!("后端地址 {}", started.url));

            app.manage(BackendState {
                url: started.url,
                data_dir,
                error: started.error,
            });
            app.manage(BackendProcess(Mutex::new(started.child)));
            Ok(())
        })
        .on_window_event(|window, event| {
            // 主窗口关闭时 kill Python 子进程
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                if let Ok(mut guard) = window.state::<BackendProcess>().0.lock() {
                    sidecar::kill_backend(&mut guard);
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            ping,
            test_llm,
            api_request,
            get_backend_url,
            get_data_dir,
            get_backend_error,
            open_data_dir,
            backend_ready
        ])
        .build(tauri::generate_context!())
        .expect("error while building Book Soul desktop application");

    app.run(|app_handle, event| {
        // 兜底：窗口没走 CloseRequested 就整个退出了（任务管理器强杀 / 崩溃），
        // 也要确保后端不会变孤儿进程。
        //
        // ⚠️ 这里必须**同步**杀：正常关窗时 CloseRequested 已经把句柄取走了
        // （slot = None，这里是 no-op）；走到这里说明是异常退出路径，
        // 若还 spawn 线程，app 一退出线程就被连带杀掉 → 后端成孤儿。
        if matches!(event, tauri::RunEvent::Exit) {
            if let Some(state) = app_handle.try_state::<BackendProcess>() {
                if let Ok(mut guard) = state.0.lock() {
                    if let Some(child) = guard.take() {
                        sidecar::kill_backend_child(child);
                    }
                }
            }
        }
    });
}
