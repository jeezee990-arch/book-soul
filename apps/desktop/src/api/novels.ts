import { callApi } from "./index";
import type { Novel } from "@/lib/types";

export type NovelCreate = Omit<
  Novel,
  "id" | "created_at" | "updated_at" | "current_version_id" | "word_count" | "growth_arc" | "is_active" | "novel_id"
> & {
  // 实际创建只需要必填字段，其他可选
};

export type NovelUpdate = Partial<NovelCreate>;

export interface ExportMdResponse {
  filename: string;
  content: string;
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
};
