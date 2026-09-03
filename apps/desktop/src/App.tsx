import { useState } from "react";
import { testLlm, type LlmTestResponse } from "./api/llm";

/**
 * Book Soul — Phase 0 模块 0.10：Hello World 端到端验证
 *
 * 数据流：点击按钮 → invoke("test_llm") → Rust → Python /llm/test → minimax → 返回
 */
function App() {
  const [prompt, setPrompt] = useState("用一句话介绍《凡人修仙传》");
  const [result, setResult] = useState<LlmTestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleTest = async () => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await testLlm({ prompt });
      setResult(r);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-200 dark:from-slate-900 dark:to-slate-800 flex flex-col items-center justify-center p-8">
      <div className="max-w-2xl w-full text-center space-y-6">
        <div className="space-y-2">
          <h1 className="text-5xl font-bold bg-gradient-to-r from-indigo-500 to-purple-600 bg-clip-text text-transparent">
            Book Soul
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Phase 0 模块 0.10 · 端到端 Hello World
          </p>
        </div>

        <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-lg p-6 space-y-4 text-left">
          <label className="block">
            <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
              提示词
            </span>
            <input
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              disabled={busy}
              className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 px-3 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              placeholder="用一句话介绍《凡人修仙传》"
            />
          </label>

          <button
            type="button"
            onClick={handleTest}
            disabled={busy || !prompt.trim()}
            className="w-full px-4 py-2 rounded-lg bg-indigo-500 text-white font-medium hover:bg-indigo-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {busy ? "调用中..." : "测试 LLM"}
          </button>

          {error && (
            <div className="text-sm font-mono p-3 rounded bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-200 whitespace-pre-wrap">
              ✗ {error}
            </div>
          )}

          {result && (
            <div className="space-y-2">
              <div className="text-xs text-slate-500 dark:text-slate-400 flex gap-4 flex-wrap">
                <span>
                  provider: <code className="text-slate-700 dark:text-slate-300">{result.provider}</code>
                </span>
                <span>
                  model: <code className="text-slate-700 dark:text-slate-300">{result.model}</code>
                </span>
                <span>
                  tokens:{" "}
                  <code className="text-slate-700 dark:text-slate-300">
                    {result.prompt_tokens}+{result.completion_tokens}={result.total_tokens}
                  </code>
                </span>
              </div>
              <div className="text-sm p-4 rounded-lg bg-slate-50 dark:bg-slate-900 text-slate-800 dark:text-slate-200 whitespace-pre-wrap">
                {result.content}
              </div>
            </div>
          )}
        </div>

        <p className="text-xs text-slate-400">
          调用链：UI → Tauri Cmd → Rust (reqwest) → Python FastAPI → minimax
        </p>
      </div>
    </div>
  );
}

export default App;
