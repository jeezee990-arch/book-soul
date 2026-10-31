import { callApi } from "./index";
import type { Novel } from "@/lib/types";

export type NovelCreate = Omit<
  Novel,
  | "id"
  | "created_at"
  | "updated_at"
  | "current_version_id"
  | "word_count"
  | "growth_arc"
  | "is_active"
  | "novel_id"
  // sort_order 由「手动排序」接口维护，创建时不传
  | "sort_order"
> & {
  // 实际创建只需要必填字段，其他可选
};

export type NovelUpdate = Partial<NovelCreate>;

export interface ExportMdResponse {
  filename: string;
  content: string;
}

export interface ExportFileResponse {
  filename: string;
  mime: string;
  content_b64: string;
}

/** 手动排序的结果（后端按新顺序返回作品）。 */
export interface NovelReorderResponse {
  items: Novel[];
}

export const novelsApi = {
  list: (params?: { genre?: string; status?: string }) => {
    const q = new URLSearchParams();
    if (params?.genre) q.set("genre", params.genre);
    if (params?.status) q.set("status", params.status);
    const qs = q.toString();
    return callApi<Novel[]>("GET", `/novels${qs ? `?${qs}` : ""}`);
  },
  get: (id: number) => callApi<Novel>("GET", `/novels/${id}`),
  create: (data: NovelCreate) => callApi<Novel>("POST", "/novels", data),
  update: (id: number, data: NovelUpdate) =>
    callApi<Novel>("PATCH", `/novels/${id}`, data),
  remove: (id: number) => callApi<null>("DELETE", `/novels/${id}`),
  /**
   * 手动排序（2026-10-30 素材库管理）。
   *
   * `ids` 是**完整**的作品 id 顺序 —— 后端把 sort_order 重排成下标，
   * 没在列表里的作品会被排到后面。所以要传全量，别只传可见的那几条
   * （只传可见子集会把隐藏作品的顺序冲掉）。
   */
  reorder: (ids: number[]) =>
    callApi<NovelReorderResponse>("POST", "/novels/reorder", { ids }),
  /** Phase 3.8：导出作品为 markdown 文件，触发浏览器下载 */
  exportMarkdown: async (id: number, _novelName: string): Promise<void> => {
    const resp = await callApi<ExportMdResponse>(
      "GET",
      `/novels/${id}/export-md`,
    );
    // 构造 Blob 触发下载
    const blob = new Blob([resp.content], {
      type: "text/markdown;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = resp.filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
  /** Phase 4.7：多格式导出（md / html / docx）。 */
  export: (id: number, format: "md" | "html" | "docx") =>
    callApi<ExportFileResponse>("GET", `/novels/${id}/export?format=${format}`),
};

/** Phase 4.7：把后端 ExportFileResponse 解码成 Blob 触发浏览器下载。 */
export function downloadExportFile(file: ExportFileResponse): void {
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
}
