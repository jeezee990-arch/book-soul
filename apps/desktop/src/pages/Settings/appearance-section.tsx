/**
 * 设置 · 外观分区。
 *
 * 编辑区默认**固定浅色纸面**（不随主题切换）——
 * 深色外壳 + 浅色纸面对长篇写作最舒服；
 * 也提供"跟随主题"选项给喜欢全深色的用户。
 *
 * 状态归属：主题在 `useUIStore`（AppShell 启动时读后端设置覆盖），
 * 纸面模式 / 字号在 `useAppearanceStore`（纯本地，localStorage 持久化）。
 * **本组件只管渲染**，DOM 应用统一由 AppShell 做 —— 避免"状态显示跟随、
 * 实际 DOM 没跟随"这种割裂。
 */

import { useState } from "react";
import { toast } from "sonner";
import { settingsApi, type UITheme } from "@/api/settings";
import { useUIStore } from "@/stores/uiStore";
import { useAppearanceStore } from "@/stores/appearance-store";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** 主题选项。 */
const THEMES: { value: UITheme; label: string }[] = [
  { value: "dark", label: "深色" },
  { value: "light", label: "浅色" },
];

export default function AppearanceSection() {
  const theme = useUIStore((s) => s.theme);
  const setTheme = useUIStore((s) => s.setTheme);
  const paperMode = useAppearanceStore((s) => s.paperMode);
  const setPaperMode = useAppearanceStore((s) => s.setPaperMode);
  const fontSize = useAppearanceStore((s) => s.fontSize);
  const setFontSize = useAppearanceStore((s) => s.setFontSize);
  const [saving, setSaving] = useState(false);

  async function handleSaveTheme() {
    setSaving(true);
    try {
      await settingsApi.update({ ui: { theme } });
      toast.success("主题已保存");
    } catch (e: unknown) {
      toast.error("保存失败", { description: String(e) });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <h3 className="text-[14px] font-semibold">外观</h3>
      <p className="mt-0.5 mb-4 text-[11.5px] leading-relaxed text-neutral-400">
        编辑区默认使用浅色纸面，长时间写作不刺眼。
      </p>

      <div className="mb-4 flex items-center gap-3">
        <span className="w-24 shrink-0 text-[12px] text-neutral-500">主题</span>
        <div className="flex gap-0.5 rounded-lg border border-neutral-200 bg-neutral-50 p-0.5 dark:border-neutral-800 dark:bg-neutral-800/40">
          {THEMES.map((t) => (
            <button
              key={t.value}
              type="button"
              onClick={() => setTheme(t.value)}
              className={cn(
                "rounded-md px-4 py-1.5 text-[11.5px] transition-colors",
                theme === t.value
                  ? "bg-white font-medium shadow-sm dark:bg-neutral-700 dark:text-neutral-50"
                  : "text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
        <Button size="sm" onClick={() => void handleSaveTheme()} disabled={saving}>
          保存
        </Button>
      </div>

      <div className="mb-4 flex items-center gap-3">
        <span className="w-24 shrink-0 text-[12px] text-neutral-500">编辑区</span>
        <div className="flex gap-0.5 rounded-lg border border-neutral-200 bg-neutral-50 p-0.5 dark:border-neutral-800 dark:bg-neutral-800/40">
          {(
            [
              { v: "paper", t: "纸面浅色" },
              { v: "follow", t: "跟随主题" },
            ] as const
          ).map((o) => (
            <button
              key={o.v}
              type="button"
              onClick={() => setPaperMode(o.v)}
              className={cn(
                "rounded-md px-3.5 py-1.5 text-[11.5px] transition-colors",
                paperMode === o.v
                  ? "bg-white font-medium shadow-sm dark:bg-neutral-700 dark:text-neutral-50"
                  : "text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200",
              )}
            >
              {o.t}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <span className="w-24 shrink-0 text-[12px] text-neutral-500">正文字号</span>
        <input
          type="range"
          min={13}
          max={22}
          step={0.5}
          value={fontSize}
          onChange={(e) => setFontSize(Number(e.target.value))}
          className="w-48 accent-indigo-500"
        />
        <span className="font-mono text-[12px] text-neutral-500">
          {fontSize} px
        </span>
        <span className="text-[11px] text-neutral-400">行高 1.95</span>
      </div>
    </div>
  );
}
