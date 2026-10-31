/**
 * 上下文面板（写作页右栏 332px）。
 *
 * 5 个 Tab 全部围绕"当前章节"展开：
 * 生成 / 重写 / 人物 / 大纲 / 版本
 *
 * 重设计要点：人物卡、大纲原本是独立页面（或根本没有页面），
 * 现在统一收进右栏 —— 用户不用跳页，章节上下文始终在。
 */

import {
  ScrollText,
  Sparkles,
  Users,
  Wand2,
  History,
} from "lucide-react";
import type { Chapter, Novel } from "@/lib/types";
import type { PanelTab } from "./types";
import type { ChapterStreamApi } from "./use-chapter-stream";
import GenerateTab from "./tabs/generate-tab";
import RewriteTab from "./tabs/rewrite-tab";
import CharacterTab from "./tabs/character-tab";
import OutlineTab from "./tabs/outline-tab";
import VersionTab from "./tabs/version-tab";
import { cn } from "@/lib/utils";

interface TabDef {
  key: PanelTab;
  label: string;
  icon: typeof Sparkles;
}

const TABS: TabDef[] = [
  { key: "generate", label: "生成", icon: Sparkles },
  { key: "rewrite", label: "重写", icon: Wand2 },
  { key: "characters", label: "人物", icon: Users },
  { key: "outline", label: "大纲", icon: ScrollText },
  { key: "versions", label: "版本", icon: History },
];

interface Props {
  tab: PanelTab;
  onTabChange: (tab: PanelTab) => void;
  novel: Novel | null;
  chapter: Chapter | null;
  stream: ChapterStreamApi;
  /** 当前选区（重写用） */
  selection: { from: number; to: number; text: string } | null;
  /** 章节版本号变化时触发刷新（版本 Tab 用） */
  versionTick: number;
}

export default function ContextPanel({
  tab,
  onTabChange,
  novel,
  chapter,
  stream,
  selection,
  versionTick,
}: Props) {
  return (
    <aside className="flex w-[332px] shrink-0 flex-col border-l border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900">
      {/* Tab 头 */}
      <div className="grid shrink-0 grid-cols-5 border-b border-neutral-200 dark:border-neutral-800">
        {TABS.map((t) => {
          const on = t.key === tab;
          return (
            <button
              key={t.key}
              type="button"
              onClick={() => onTabChange(t.key)}
              title={t.label}
              className={cn(
                "relative border-b-2 py-2.5 text-[11px] transition-colors",
                on
                  ? "border-indigo-500 font-medium text-indigo-600 dark:text-indigo-300"
                  : "border-transparent text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200",
              )}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Tab 内容 */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {tab === "generate" ? (
          <GenerateTab
            novel={novel}
            chapter={chapter}
            stream={stream}
            onSwitchTab={onTabChange}
          />
        ) : null}

        {tab === "rewrite" ? (
          <RewriteTab
            chapter={chapter}
            stream={stream}
            selection={selection}
          />
        ) : null}

        {tab === "characters" ? <CharacterTab novel={novel} /> : null}

        {tab === "outline" ? (
          <OutlineTab novel={novel} versionTick={versionTick} />
        ) : null}

        {tab === "versions" ? (
          <VersionTab chapter={chapter} versionTick={versionTick} />
        ) : null}
      </div>
    </aside>
  );
}
