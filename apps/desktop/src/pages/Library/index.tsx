/**
 * 素材库（作品 / 灵感 / 导入）。
 *
 * 2026-10 UI 重设计：旧「作品库」有 4 个 Tab（作品 / 藏书馆 / 本地扫描 / 灵感库），
 * 其中「作品」和「藏书馆」是同一份数据的两种过滤 —— 合并为一份。
 * 现在 3 个 Tab：作品 / 灵感 / 导入。
 */

import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { BookOpen, FolderSearch, Lightbulb, Plus } from "lucide-react";
import { toast } from "sonner";
import type { Novel } from "@/lib/types";
import type { InspirationDetail as InspirationDetailType } from "@/api/inspirations";
import { useNovelsStore } from "@/stores/novels-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import LibraryList from "./LibraryList";
import LibraryDetail from "./LibraryDetail";
import InspirationList from "./InspirationList";
import InspirationDetail from "./InspirationDetail";
import ScannerConfig from "./ScannerConfig";
import CreateNovelDialog from "./CreateNovelDialog";
import { cn } from "@/lib/utils";

type Tab = "works" | "inspirations" | "import";

const TABS: { key: Tab; label: string; icon: typeof BookOpen }[] = [
  { key: "works", label: "作品", icon: BookOpen },
  { key: "inspirations", label: "灵感", icon: Lightbulb },
  { key: "import", label: "导入", icon: FolderSearch },
];

export default function Library() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const refreshNovels = useNovelsStore((s) => s.refresh);
  const setNovelId = useWorkspaceStore((s) => s.setNovelId);

  const [tab, setTab] = useState<Tab>(
    (searchParams.get("tab") as Tab) ?? "works",
  );
  const [selectedNovel, setSelectedNovel] = useState<Novel | null>(null);
  const [novelDetailOpen, setNovelDetailOpen] = useState(false);
  const [typeFilter, setTypeFilter] = useState<string | null>(null);
  const [selectedInsp, setSelectedInsp] = useState<InspirationDetailType | null>(
    null,
  );
  const [inspDetailOpen, setInspDetailOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(searchParams.get("new") === "1");

  // 顶栏「新建作品」会带 ?new=1 过来
  useEffect(() => {
    if (searchParams.get("new") === "1") {
      setCreateOpen(true);
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  function switchTab(next: Tab) {
    setTab(next);
    setSearchParams(next === "works" ? {} : { tab: next }, { replace: true });
  }

  /** 继续写：切到写作页并选中该作品 */
  function handleContinue(n: Novel) {
    setNovelId(n.id);
    navigate("/");
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* Tab 头 */}
      <div className="flex h-11 shrink-0 items-end gap-0.5 border-b border-neutral-200 bg-white px-6 dark:border-neutral-800 dark:bg-neutral-900">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => switchTab(t.key)}
            className={cn(
              "flex h-11 items-center gap-1.5 border-b-2 px-3.5 text-[12.5px] transition-colors",
              tab === t.key
                ? "border-indigo-500 font-medium text-neutral-900 dark:text-neutral-100"
                : "border-transparent text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200",
            )}
          >
            <t.icon className="h-3.5 w-3.5" />
            {t.label}
          </button>
        ))}

        {tab === "works" ? (
          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            className="mb-1.5 ml-auto inline-flex h-7 items-center gap-1.5 rounded-lg bg-indigo-600 px-2.5 text-[11.5px] font-medium text-white transition-colors hover:bg-indigo-700"
          >
            <Plus className="h-3.5 w-3.5" />
            新建作品
          </button>
        ) : null}
      </div>

      {/* 内容 */}
      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
        {tab === "works" ? (
          <LibraryList
            onSelect={(n) => {
              setSelectedNovel(n);
              setNovelDetailOpen(true);
            }}
            onContinue={handleContinue}
          />
        ) : null}

        {tab === "inspirations" ? (
          <InspirationList
            typeFilter={typeFilter}
            onTypeFilterChange={setTypeFilter}
            onSelect={(d) => {
              setSelectedInsp(d);
              setInspDetailOpen(true);
            }}
          />
        ) : null}

        {tab === "import" ? (
          <ScannerConfig
            onImported={() => {
              void refreshNovels();
              switchTab("works");
              toast.success("导入完成", { description: "可在「作品」里看到新导入的作品" });
            }}
          />
        ) : null}
      </div>

      <LibraryDetail
        open={novelDetailOpen}
        onOpenChange={setNovelDetailOpen}
        novel={selectedNovel}
      />
      <InspirationDetail
        open={inspDetailOpen}
        onOpenChange={setInspDetailOpen}
        detail={selectedInsp}
      />
      <CreateNovelDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={(n) => {
          void refreshNovels();
          setSelectedNovel(n);
        }}
      />
    </div>
  );
}
