import { useState } from "react";
import { BookOpen, BookText, Lightbulb, FolderSearch } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import type { Novel } from "@/lib/types";
import LibraryList from "./LibraryList";
import LibraryDetail from "./LibraryDetail";
import InspirationList from "./InspirationList";
import InspirationDetail from "./InspirationDetail";
import ScannerConfig from "./ScannerConfig";
import type { InspirationDetail as InspirationDetailType } from "@/api/inspirations";

export default function Library() {
  const [tab, setTab] = useState<"novels" | "library" | "scanner" | "inspirations">(
    "novels",
  );
  const [selectedNovel, setSelectedNovel] = useState<Novel | null>(null);
  const [novelDetailOpen, setNovelDetailOpen] = useState(false);
  const [typeFilter, setTypeFilter] = useState<string | null>(null);
  const [selectedInsp, setSelectedInsp] = useState<InspirationDetailType | null>(
    null,
  );
  const [inspDetailOpen, setInspDetailOpen] = useState(false);

  return (
    <section className="space-y-6">
      <header className="flex items-center justify-between">
        <div className="space-y-1.5">
          <h1 className="text-2xl font-semibold tracking-tight">作品库</h1>
          <p className="text-sm text-neutral-500 dark:text-neutral-400">
            作品管理 · 藏书阅读 · 本地扫描 · 灵感库。
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => toast.info("敬请期待", { description: "Phase 4 接入" })}
        >
          新建作品
        </Button>
      </header>

      <Tabs
        value={tab}
        onValueChange={(v) =>
          setTab(v as "novels" | "library" | "scanner" | "inspirations")
        }
      >
        <TabsList>
          <TabsTrigger value="novels">
            <BookOpen className="mr-1.5 h-3.5 w-3.5" />
            作品
          </TabsTrigger>
          <TabsTrigger value="library">
            <BookText className="mr-1.5 h-3.5 w-3.5" />
            藏书馆
          </TabsTrigger>
          <TabsTrigger value="scanner">
            <FolderSearch className="mr-1.5 h-3.5 w-3.5" />
            本地扫描
          </TabsTrigger>
          <TabsTrigger value="inspirations">
            <Lightbulb className="mr-1.5 h-3.5 w-3.5" />
            灵感库
          </TabsTrigger>
        </TabsList>

        <TabsContent value="novels" className="mt-4">
          <LibraryList
            withChaptersOnly={false}
            onSelect={(n) => {
              setSelectedNovel(n);
              setNovelDetailOpen(true);
            }}
          />
        </TabsContent>

        <TabsContent value="library" className="mt-4">
          <LibraryList
            withChaptersOnly
            onSelect={(n) => {
              setSelectedNovel(n);
              setNovelDetailOpen(true);
            }}
          />
        </TabsContent>

        <TabsContent value="scanner" className="mt-4">
          <ScannerConfig
            onImported={() => {
              // 导入成功 → 跳到作品 tab
              setTab("novels");
              toast.success("可去「作品」查看新导入");
            }}
          />
        </TabsContent>

        <TabsContent value="inspirations" className="mt-4">
          <InspirationList
            typeFilter={typeFilter}
            onTypeFilterChange={setTypeFilter}
            onSelect={(d) => {
              setSelectedInsp(d);
              setInspDetailOpen(true);
            }}
          />
        </TabsContent>
      </Tabs>

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
    </section>
  );
}
