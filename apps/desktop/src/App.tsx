import { useEffect, useState } from "react";
import { HashRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import ErrorBoundary from "./components/ErrorBoundary";
import Inspiration from "./pages/Inspiration";
import Creation from "./pages/Creation";
import QualityCheck from "./pages/QualityCheck";
import Library from "./pages/Library";
import Settings from "./pages/Settings";
import Skills from "./pages/Skills";
import { getBackendError, waitBackendReady } from "./api/backend";

/**
 * 应用入口。
 *
 * 启动握手：桌面版由 Rust 侧拉起 Python 后端（随机端口），
 * 这里先等后端就绪再渲染业务页面 —— 避免首屏就 503 / 白屏。
 *
 * 失败时把 Rust 侧记录的真实原因（缺什么、路径在哪）显示出来，
 * 而不是笼统的"启动失败"让用户自己猜。
 */
export default function App() {
  const [status, setStatus] = useState<"starting" | "ready" | "failed">("starting");
  const [reason, setReason] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const ok = await waitBackendReady(30_000);
      if (cancelled) return;
      if (ok) {
        setStatus("ready");
        return;
      }
      // 没就绪：去问 Rust 到底为什么
      const err = await getBackendError();
      if (cancelled) return;
      setReason(typeof err === "string" && err.length > 0 ? err : null);
      setStatus("failed");
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (status === "starting") {
    return <StartupScreen failed={false} reason={null} />;
  }
  if (status === "failed") {
    return <StartupScreen failed reason={reason} />;
  }

  return (
    <ErrorBoundary>
      <HashRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Inspiration />} />
            <Route path="/creation" element={<Creation />} />
            <Route path="/quality" element={<QualityCheck />} />
            <Route path="/library" element={<Library />} />
            <Route path="/skills" element={<Skills />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Routes>
      </HashRouter>
    </ErrorBoundary>
  );
}

/** 启动 / 失败提示屏。 */
function StartupScreen({ failed, reason }: { failed: boolean; reason: string | null }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-neutral-50 text-center dark:bg-neutral-950">
      {failed ? (
        <>
          <h1 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">
            写作引擎启动失败
          </h1>
          <p className="max-w-md text-sm text-neutral-500 dark:text-neutral-400">
            后端服务在 30 秒内没有就绪。请关闭应用后重试；
            若反复失败，请查看应用目录下的 <code>data/logs/backend.log</code>。
          </p>
          {reason ? (
            <pre className="max-w-2xl overflow-auto whitespace-pre-wrap rounded-md border border-neutral-200 bg-white p-3 text-left text-xs text-neutral-700 dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-300">
              {reason}
            </pre>
          ) : null}
        </>
      ) : (
        <>
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-neutral-300 border-t-neutral-700 dark:border-neutral-700 dark:border-t-neutral-200" />
          <p className="text-sm text-neutral-500 dark:text-neutral-400">
            正在启动写作引擎…
          </p>
        </>
      )}
    </div>
  );
}
