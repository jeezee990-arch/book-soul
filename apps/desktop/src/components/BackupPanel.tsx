import { useRef, useState } from "react";
import { Download, Upload, AlertTriangle } from "lucide-react";
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
import { backupApi } from "@/api/backup";
import { ApiError } from "@/api";

/** 备份 / 恢复面板（Phase 7.4）。
 *
 * - 导出：把 data_dir 打包为 zip，触发浏览器下载
 * - 导入：选本地 .zip → base64 → 调 API
 *
 * 注意：导入会覆盖当前数据；恢复后建议重启 Tauri
 */
export default function BackupPanel() {
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  async function handleExport() {
    setExporting(true);
    try {
      const file = await backupApi.export();
      const binary = atob(file.content_b64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i += 1) {
        bytes[i] = binary.charCodeAt(i);
      }
      const blob = new Blob([bytes], { type: file.mime });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = file.filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast.success("备份已开始下载", { description: file.filename });
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("导出失败", { description: msg });
    } finally {
      setExporting(false);
    }
  }

  function pickFile() {
    fileInputRef.current?.click();
  }

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // 允许重选同一文件
    if (!file) return;
    if (!file.name.endsWith(".zip")) {
      toast.error("请选择 .zip 文件");
      return;
    }
    if (
      !confirm(
        `确认从 "${file.name}" 恢复？\n\n将覆盖当前所有数据。建议先做一次当前数据的备份。\n\n恢复后请重启 Tauri 桌面应用。`,
      )
    ) {
      return;
    }
    setImporting(true);
    try {
      const buf = await file.arrayBuffer();
      const bytes = new Uint8Array(buf);
      // base64 编码（用浏览器 API）
      let binary = "";
      for (let i = 0; i < bytes.length; i += 1) {
        binary += String.fromCharCode(bytes[i]);
      }
      const b64 = btoa(binary);
      const r = await backupApi.import(b64, true);
      toast.success("恢复完成", {
        description: `${r.files} 个文件${r.db_backed_up ? "（原 db 已备份为 .bak）" : ""}`,
      });
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("恢复失败", { description: msg });
    } finally {
      setImporting(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">备份 / 恢复</CardTitle>
        <CardDescription>
          导出当前所有数据为 .zip（含数据库 + 作品文件 + 日志），或从备份文件恢复
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={handleExport} disabled={exporting}>
            <Download className="mr-1.5 h-3.5 w-3.5" />
            {exporting ? "导出中…" : "导出备份"}
          </Button>
          <Button
            variant="outline"
            onClick={pickFile}
            disabled={importing}
          >
            <Upload className="mr-1.5 h-3.5 w-3.5" />
            {importing ? "恢复中…" : "从 .zip 恢复"}
          </Button>
          <Input
            ref={fileInputRef}
            type="file"
            accept=".zip,application/zip"
            onChange={handleFile}
            className="hidden"
          />
        </div>
        <div className="flex items-start gap-2 rounded-md border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/20 p-2 text-xs text-amber-800 dark:text-amber-200">
          <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
          <p>
            恢复会覆盖当前所有数据，且恢复后 SQLite 连接需要重新建立，请重启 Tauri 桌面应用。
            建议先做一次当前数据的备份。
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
