import { callApi } from "./index";
import type { Chapter, ChapterVersion } from "@/lib/types";

export type ChapterCreate = Omit<
  Chapter,
  | "id"
  | "created_at"
  | "updated_at"
  | "current_version_id"
  | "word_count"
> & { content?: string };

export type ChapterUpdate = Partial<Omit<ChapterCreate, "novel_id">>;

export const chaptersApi = {
  list: (novelId: number, params?: { status?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    const qs = q.toString();
    return callApi<Chapter[]>(
      "GET",
      `/novels/${novelId}/chapters${qs ? `?${qs}` : ""}`,
    );
  },
  get: (id: number) => callApi<Chapter>("GET", `/chapters/${id}`),
  create: (data: ChapterCreate) =>
    callApi<Chapter>("POST", `/novels/${data.novel_id}/chapters`, data),
  update: (id: number, data: ChapterUpdate) =>
    callApi<Chapter>("PATCH", `/chapters/${id}`, data),
  remove: (id: number) => callApi<null>("DELETE", `/chapters/${id}`),
  listVersions: (id: number) =>
    callApi<ChapterVersion[]>("GET", `/chapters/${id}/versions`),
  getVersion: (id: number, versionId: number) =>
    callApi<ChapterVersion>("GET", `/chapters/${id}/versions/${versionId}`),
  /** Phase 4.3/4.4：写一条新版本（流式生成 / 选区重写 / 用户编辑后）。 */
  saveContent: (
    id: number,
    data: { content: string; trigger: string; prompt?: string; metadata?: Record<string, unknown> },
  ) => callApi<ChapterVersion>("POST", `/chapters/${id}/content`, data),
};
