//! Book Soul Tauri 库入口。
//!
//! Phase 0 模块 0.7：只暴露一个 `ping` 命令验证通联。
//! 后续模块会加入：调用 Python 后端的 HTTP 客户端、文件系统操作等。

/// 健康检查命令（被前端 invoke("ping") 调用）。
#[tauri::command]
fn ping() -> String {
    "pong from Book Soul desktop".to_string()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![ping])
        .run(tauri::generate_context!())
        .expect("error while running Book Soul desktop application");
}
