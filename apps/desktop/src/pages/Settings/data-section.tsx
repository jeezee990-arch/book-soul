/**
 * 设置 · 数据与备份分区。
 *
 * 旧设置页把「数据目录」写成一坨说明文字（只读，且没说清路径在哪），
 * 这里改成显示**真实路径**（后端 GET /settings 现在会返回 data_dir），
 * 并提供复制路径按钮。
 */

import { useEffect, useState } from "react";
import { Copy, FolderOpen } from "lucide-react";
import { toast } from "sonner";
import { settingsApi, type Settings } from "@/api/settings";
import { ApiError } from "@/api";
import BackupPanel from "@/components/BackupPanel";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function DataSection() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [encryption, setEncryption] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    settingsApi
      .get()
      .then((s) => {
        if (cancelled) return;
        setSettings(s);
        setEncryption(s.security.encryption_enabled);
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          toast.error("加载设置失败", {
            description: e instanceof ApiError ? e.message : String(e),
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSaveSecurity() {
    setSaving(true);
    try {
      const updated = await settingsApi.update({
        security: { encryption_enabled: encryption },
      });
      setSettings(updated);
      toast.success("已保存", { description: "加密开关需要重启服务后生效。" });
    } catch (e: unknown) {
      toast.error("保存失败", {
        description: e instanceof ApiError ? e.message : String(e),
      });
    } finally {
      setSaving(false);
    }
  }

  async function handleCopyPath() {
    const path = settings?.data_dir;
    if (!path) return;
    try {
      await navigator.clipboard.writeText(path);
      toast.success("路径已复制");
    } catch {
      toast.error("复制失败", { description: path });
    }
  }

  return (
    <div>
      <h3 className="text-[14px] font-semibold">数据与备份</h3>
      <p className="mt-0.5 mb-4 text-[11.5px] leading-relaxed text-neutral-400">
        打包版为便携模式：整个文件夹拷走就是完整迁移。
      </p>

      {/* 数据目录 */}
      <div className="mb-5 flex items-start gap-3">
        <span className="w-24 shrink-0 pt-2 text-[12px] text-neutral-500">
          数据目录
        </span>
        <div className="min-w-0 flex-1">
          <div
            className={cn(
              "rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2",
              "font-mono text-[11px] break-all text-neutral-600",
              "dark:border-neutral-800 dark:bg-neutral-800/40 dark:text-neutral-300",
            )}
          >
            {settings?.data_dir || "（后端未返回）"}
          </div>
          <p className="mt-1.5 text-[11px] text-neutral-400">
            打包版：exe 同级的 <code>data/</code>；开发版：仓库下的{" "}
            <code>data/dev</code>。由环境变量{" "}
            <code className="font-mono">BOOK_SOUL_DATA_DIR</code> 决定。
          </p>
          <div className="mt-2 flex gap-2">
            <Button size="sm" variant="outline" onClick={() => void handleCopyPath()}>
              <Copy className="mr-1.5 h-3.5 w-3.5" />
              复制路径
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() =>
                toast.info("请到系统文件管理器打开该目录", {
                  description: settings?.data_dir,
                })
              }
            >
              <FolderOpen className="mr-1.5 h-3.5 w-3.5" />
              在文件夹中显示
            </Button>
          </div>
        </div>
      </div>

      {/* 备份 */}
      <div className="mb-5 border-t border-neutral-200 pt-4 dark:border-neutral-800">
        <BackupPanel />
      </div>

      {/* 加密 */}
      <div className="border-t border-neutral-200 pt-4 dark:border-neutral-800">
        <div className="flex items-center gap-3">
          <span className="w-24 shrink-0 text-[12px] text-neutral-500">加密</span>
          <Switch
            checked={encryption}
            onCheckedChange={setEncryption}
            disabled={saving}
            aria-label="启用 Fernet 加密"
          />
          <span className="text-[11.5px] text-neutral-400">
            启用 Fernet 加密敏感字段 · 需重启服务生效
          </span>
        </div>
        <div className="mt-3 flex justify-end">
          <Button
            onClick={() => void handleSaveSecurity()}
            disabled={saving}
            size="sm"
          >
            保存
          </Button>
        </div>
      </div>
    </div>
  );
}
