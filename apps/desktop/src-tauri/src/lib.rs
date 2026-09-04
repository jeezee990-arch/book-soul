//! Book Soul Tauri 库入口。
//!
//! Phase 0 模块 0.7：只暴露一个 `ping` 命令验证通联。
//! 后续模块会加入：调用 Python 后端的 HTTP 客户端、文件系统操作等。

use serde::{Deserialize, Serialize};
use serde_json::Value;

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
        .timeout(std::time::Duration::from_secs(30))
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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![ping, test_llm, api_request])
        .run(tauri::generate_context!())
        .expect("error while running Book Soul desktop application");
}
