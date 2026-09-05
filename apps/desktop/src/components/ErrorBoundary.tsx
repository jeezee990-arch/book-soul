import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/** 全局错误边界（Phase 7.3）。
 *
 * 捕获 React 渲染错误，避免白屏。点"重试"重新加载页面。
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // 上报（生产可接 Sentry 等）
    // eslint-disable-next-line no-console
    console.error("UI ErrorBoundary caught:", error, info);
  }

  handleRetry = () => {
    this.setState({ error: null });
  };

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-neutral-50 dark:bg-neutral-950 p-8">
          <div className="max-w-md w-full rounded-lg border border-rose-200 dark:border-rose-800 bg-white dark:bg-neutral-900 p-6 space-y-4 shadow-sm">
            <div className="flex items-center gap-2 text-rose-600 dark:text-rose-400">
              <AlertTriangle className="h-5 w-5" />
              <h1 className="text-lg font-semibold">界面出错了</h1>
            </div>
            <p className="text-sm text-neutral-600 dark:text-neutral-400">
              渲染时发生未捕获错误。已记录到控制台。可点下方按钮恢复。
            </p>
            <pre className="text-xs font-mono text-neutral-500 dark:text-neutral-500 bg-neutral-50 dark:bg-neutral-950 p-2 rounded border border-neutral-200 dark:border-neutral-800 max-h-40 overflow-auto whitespace-pre-wrap break-words">
              {this.state.error.message}
              {"\n\n"}
              {this.state.error.stack?.split("\n").slice(0, 5).join("\n")}
            </pre>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={this.handleRetry}>
                <RotateCw className="mr-1.5 h-3 w-3" />
                重试
              </Button>
              <Button size="sm" onClick={this.handleReload}>
                重新加载
              </Button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
