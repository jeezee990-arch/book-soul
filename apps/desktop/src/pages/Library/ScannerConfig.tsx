import { useState } from "react";
import { Search, FolderInput, FileText, Hash } from "lucide-react";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import LoadingSkeleton from "@/components/layout/LoadingSkeleton";
import ErrorState from "@/components/layout/ErrorState";
import EmptyState from "@/components/layout/EmptyState";
import { scannerApi, type DetectedNovel } from "@/api/scanner";
import { ApiError } from "@/api";

const GENRES = [
  { value: "xiuxian", label: "修仙" },
  { value: "dushi", label: "都市" },
  { value: "xuanyi", label: "悬疑" },
  { value: "yanqing", label: "言情" },
];

interface Props {
  /** 导入成功后回调（让父 tab 刷新） */
  onImported?: (novelId: number) => void;
}

/** 本地扫描（Phase 6.3）：
 * - 输入目录 → 扫描 → 显示检测到的小说
 * - 每个小说可预览 / 导入
 */
export default function ScannerConfig({ onImported }: Props) {
  const [scanPath, setScanPath] = useState("");
  const [genre, setGenre] = useState("xiuxian");
  const [results, setResults] = useState<DetectedNovel[]>([]);
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);
  const [importingPath, setImportingPath] = useState<string | null>(null);
  const [expandedPath, setExpandedPath] = useState<string | null>(null);

  async function handleScan() {
    const path = scanPath.trim();
    if (!path) {
      toast.error("请输入目录路径");
      return;
    }
    setScanning(true);
    setScanError(null);
    setResults([]);
    try {
      const r = await scannerApi.scan(path, 3);
      setResults(r.novels);
      if (r.novels.length === 0) {
        toast.info("未检测到小说", {
          description: "目录里没找到 ≥3 个含章节标记的 .md 文件",
        });
      } else {
        toast.success(`检测到 ${r.novels.length} 部疑似小说`);
      }
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      setScanError(msg);
      toast.error("扫描失败", { description: msg });
    } finally {
      setScanning(false);
    }
  }

  async function handleImport(novel: DetectedNovel) {
    setImportingPath(novel.dir_path);
    try {
      const r = await scannerApi.import(novel.dir_path, genre);
      toast.success("已导入", {
        description: `${r.name} (${r.chapter_count} 章)`,
      });
      onImported?.(r.novel_id);
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("导入失败", { description: msg });
    } finally {
      setImportingPath(null);
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">扫描本地小说目录</CardTitle>
          <CardDescription>
            输入本地小说目录（多个 .md 文件，含「第X章」或「Chapter X」标记）→
            系统自动检测 → 选导入
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Input
              value={scanPath}
              onChange={(e) => setScanPath(e.target.value)}
              placeholder="D:\novels\凡人修仙传"
              className="flex-1 min-w-[280px]"
              disabled={scanning}
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleScan();
              }}
            />
            <Select value={genre} onValueChange={setGenre}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {GENRES.map((g) => (
                  <SelectItem key={g.value} value={g.value}>
                    {g.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button onClick={handleScan} disabled={scanning}>
              <Search className="mr-1.5 h-3.5 w-3.5" />
              {scanning ? "扫描中…" : "开始扫描"}
            </Button>
          </div>
          <p className="text-[10px] text-neutral-500">
            提示：递归深度最多 3 层；单次最多返回 200 部；隐藏目录自动跳过
          </p>
        </CardContent>
      </Card>

      {scanError && <ErrorState message={scanError} />}

      {scanning && <LoadingSkeleton rows={3} height={80} />}

      {!scanning && !scanError && results.length === 0 && (
        <EmptyState
          icon="🔍"
          title="还没有扫描结果"
          description="输入目录路径后点「开始扫描」"
        />
      )}

      {!scanning && results.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs text-neutral-500">
            检测到 {results.length} 部
          </div>
          {results.map((d) => {
            const open = expandedPath === d.dir_path;
            return (
              <Card key={d.dir_path}>
                <CardHeader>
                  <div className="flex items-center justify-between gap-2">
                    <div className="space-y-0.5">
                      <CardTitle className="text-sm flex items-center gap-2">
                        <FileText className="h-3.5 w-3.5 text-neutral-400" />
                        {d.title}
                      </CardTitle>
                      <p className="text-[10px] text-neutral-500 font-mono">
                        {d.dir_path}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-[10px] text-neutral-500 flex items-center gap-1">
                        <Hash className="h-3 w-3" />
                        {d.chapter_count} 章 · {d.total_words.toLocaleString()} 字
                      </span>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 px-2 text-xs"
                        onClick={() => setExpandedPath(open ? null : d.dir_path)}
                      >
                        {open ? "收起" : "展开"}
                      </Button>
                      <Button
                        size="sm"
                        className="h-7 px-2 text-xs"
                        onClick={() => handleImport(d)}
                        disabled={importingPath === d.dir_path}
                      >
                        <FolderInput className="mr-1.5 h-3 w-3" />
                        {importingPath === d.dir_path ? "导入中…" : "导入"}
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                {open && (
                  <CardContent className="space-y-2 pt-0">
                    {d.chapters.map((c, idx) => (
                      <div
                        key={c.path}
                        className="rounded-md border border-neutral-100 dark:border-neutral-900 p-2 text-xs"
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-medium">
                            {idx + 1}. {c.title}
                          </span>
                          <span className="text-[10px] text-neutral-500">
                            {c.word_count.toLocaleString()} 字
                          </span>
                        </div>
                        {c.preview && (
                          <p className="text-[10px] text-neutral-500 line-clamp-2">
                            {c.preview}
                          </p>
                        )}
                      </div>
                    ))}
                  </CardContent>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
