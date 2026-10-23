/**
 * 设置（4 个分区）。
 *
 * 2026-10 UI 重设计：从一长条卡片墙改成**左侧分区导航 + 右侧内容**：
 * LLM 与密钥 / 数据与备份 / AI 增强 / 外观。
 * 原「Skills」一级页面降级为「AI 增强」分区。
 */

import { useState } from "react";
import { Database, Palette, Sparkles, Zap } from "lucide-react";
import LlmSection from "./llm-section";
import DataSection from "./data-section";
import AiSection from "./ai-section";
import AppearanceSection from "./appearance-section";
import { cn } from "@/lib/utils";

type Section = "llm" | "data" | "ai" | "appearance";

const SECTIONS: {
  key: Section;
  label: string;
  icon: typeof Zap;
}[] = [
  { key: "llm", label: "LLM 与密钥", icon: Zap },
  { key: "data", label: "数据与备份", icon: Database },
  { key: "ai", label: "AI 增强", icon: Sparkles },
  { key: "appearance", label: "外观", icon: Palette },
];

export default function Settings() {
  const [section, setSection] = useState<Section>("llm");

  return (
    <div className="flex h-full min-h-0">
      {/* 分区导航 */}
      <nav className="w-[180px] shrink-0 border-r border-neutral-200 bg-white px-2.5 py-4 dark:border-neutral-800 dark:bg-neutral-900">
        {SECTIONS.map((s) => (
          <button
            key={s.key}
            type="button"
            onClick={() => setSection(s.key)}
            className={cn(
              "mb-0.5 flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[12.5px] transition-colors",
              section === s.key
                ? "bg-indigo-500/10 font-medium text-indigo-700 dark:text-indigo-300"
                : "text-neutral-500 hover:bg-neutral-100 hover:text-neutral-800 dark:text-neutral-400 dark:hover:bg-neutral-800 dark:hover:text-neutral-100",
            )}
          >
            <s.icon className="h-3.5 w-3.5 shrink-0" />
            {s.label}
          </button>
        ))}
      </nav>

      {/* 内容 */}
      <div className="min-h-0 flex-1 overflow-y-auto px-9 py-6">
        <div className="max-w-[660px]">
          {section === "llm" ? <LlmSection /> : null}
          {section === "data" ? <DataSection /> : null}
          {section === "ai" ? <AiSection /> : null}
          {section === "appearance" ? <AppearanceSection /> : null}
        </div>
      </div>
    </div>
  );
}
