/**
 * 顶栏模型状态灯。
 *
 * 显示当前生效的 provider / 模型 + 连通性：
 *   绿点 = 正常　黄点 = 降级（能连但有警告）　红点 = 不可用
 *   灰点 = 尚未探活 / 未配置 Key
 *
 * 探活策略：**只在挂载时拉一次**，不轮询。
 * `/llm/health` 会真去调各 provider 的 /models 端点，轮询等于无谓地烧配额；
 * 用户想刷新可以点它跳到设置页手动测。
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { llmApi, settingsApi, type LLMProvider } from "@/api/settings";
import { cn } from "@/lib/utils";

type PillState = "ok" | "warn" | "bad" | "unknown";

const DOT_CLASS: Record<PillState, string> = {
  ok: "bg-emerald-500",
  warn: "bg-amber-500",
  bad: "bg-rose-500",
  unknown: "bg-neutral-400 dark:bg-neutral-600",
};

export default function ModelStatusPill() {
  const navigate = useNavigate();
  const [provider, setProvider] = useState<LLMProvider | null>(null);
  const [model, setModel] = useState<string>("");
  const [state, setState] = useState<PillState>("unknown");

  useEffect(() => {
    let cancelled = false;

    const probe = async () => {
      // 当前生效的 provider / model
      try {
        const s = await settingsApi.get();
        if (cancelled) return;
        setProvider(s.llm.provider);
        setModel(s.llm.model);
      } catch {
        // 设置读不到不影响启动，灯保持灰色
      }

      // 连通性
      try {
        const health = await llmApi.health();
        if (cancelled) return;
        const key = provider ?? undefined;
        if (!key) return;
        const h = health[key];
        if (!h) {
          setState("unknown");
        } else if (h.ok) {
          setState("ok");
        } else {
          // 消息里带 key 缺失的，判为"未配置"（灰），其余判为"不可用"（红）
          setState(/key|api.?key|未配置|not configured/i.test(h.message) ? "unknown" : "bad");
        }
      } catch {
        if (!cancelled) setState("unknown");
      }
    };

    void probe();
    return () => {
      cancelled = true;
    };
  }, [provider]);

  const label = provider ? `${provider} / ${model}` : "未连接";

  return (
    <button
      type="button"
      onClick={() => navigate("/settings")}
      title="查看 / 更换模型"
      className={cn(
        "flex h-7 items-center gap-2 rounded-full border border-neutral-200 bg-neutral-50 px-2.5",
        "text-[11px] text-neutral-500 transition-colors hover:bg-neutral-100",
        "dark:border-neutral-800 dark:bg-neutral-800/50 dark:text-neutral-400 dark:hover:bg-neutral-800",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500",
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", DOT_CLASS[state])} />
      <span className="max-w-[160px] truncate font-mono">{label}</span>
    </button>
  );
}
