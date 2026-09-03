import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";

/**
 * Book Soul — Phase 0 模块 0.7：Tauri 桌面壳
 * 最小可运行：显示标题 + "测试后端连接" 按钮
 * 后续模块会替换为完整应用
 */
function App() {
  const [pingResult, setPingResult] = useState<string>("未测试");
  const [busy, setBusy] = useState(false);

  const handlePing = async () => {
    setBusy(true);
    setPingResult("测试中...");
    try {
      // 调用 Rust 端定义的 ping 命令
      const result = await invoke<string>("ping");
      setPingResult(`✓ 后端通联：${result}`);
    } catch (e) {
      setPingResult(`✗ 调用失败：${String(e)}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-200 dark:from-slate-900 dark:to-slate-800 flex flex-col items-center justify-center p-8">
      <div className="max-w-xl w-full text-center space-y-6">
        <div className="space-y-2">
          <h1 className="text-5xl font-bold bg-gradient-to-r from-indigo-500 to-purple-600 bg-clip-text text-transparent">
            Book Soul
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            AI 辅助小说写作 · Phase 0 模块 0.7 · Tauri 桌面壳
          </p>
        </div>

        <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-lg p-6 space-y-4">
          <p className="text-slate-700 dark:text-slate-300">
            看到本窗口 = Tauri + React + TypeScript 已联通
          </p>

          <button
            type="button"
            onClick={handlePing}
            disabled={busy}
            className="px-4 py-2 rounded-lg bg-indigo-500 text-white font-medium hover:bg-indigo-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {busy ? "测试中..." : "测试后端连接"}
          </button>

          <div className="text-sm font-mono p-3 rounded bg-slate-100 dark:bg-slate-900 text-slate-700 dark:text-slate-300">
            {pingResult}
          </div>
        </div>

        <p className="text-xs text-slate-400">
          下一步：Phase 0.8 质量门禁 · Phase 0.9 LLM 接入 UI · Phase 1.1 实体 API
        </p>
      </div>
    </div>
  );
}

export default App;
