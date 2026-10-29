import { callApi } from "./index";
import type { StreamRequest } from "./streams";
import type { Inspiration } from "@/lib/types";

export type InspirationCreate = Omit<
  Inspiration,
  "id" | "created_at" | "pinned" | "sort_order"
>;

/**
 * 部分更新。
 *
 * 字段与后端 `InspirationUpdate`（extra="forbid"）严格对齐 ——
 * 多传一个字段后端直接 422，所以这里不能直接用 `Partial<Inspiration>`。
 */
export type InspirationUpdate = Partial<
  Omit<Inspiration, "id" | "created_at" | "sort_order" | "novel_id">
>;

// ===== Phase 3.3：剧情生成 =====

export interface PlotVersion {
  index: number;
  summary: string;
}

export interface PlotGenerationResponse {
  versions: PlotVersion[];
  provider: string;
  model: string;
}

export interface PlotGenerationRequest {
  genre: string;
  keywords: string[];
  n_versions?: number;
  user_extra?: string;
}

export interface CharacterSummary {
  id: number;
  name: string;
  role: string;
  personality: string | null;
  is_active: boolean;
}

export interface ChapterSummary {
  id: number;
  chapter_number: number;
  title: string | null;
  word_count: number;
  status: string;
}

export interface NovelContextSummary {
  id: number;
  name: string;
  genre: string;
  outline_type: string | null;
  description: string | null;
  outline_structure: Record<string, unknown> | null;
  characters: CharacterSummary[];
  chapters: ChapterSummary[];
}

export interface InspirationDetail {
  id: number;
  novel_id: number | null;
  type: string;
  source: string | null;
  tags: string[];
  content: Record<string, unknown>;
  created_at: string;
  title: string | null;
  pinned: boolean;
  sort_order: number;
  novel: NovelContextSummary | null;
}

/** 批量删除结果。 */
export interface InspirationBatchDeleteResult {
  deleted: number;
}

/** 排序结果：items 按新顺序排列。 */
export interface InspirationReorderResult {
  items: Inspiration[];
}

export const inspirationsApi = {
  list: (params?: { novel_id?: number; type?: string; tag?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.novel_id !== undefined)
      q.set("novel_id", String(params.novel_id));
    if (params?.type) q.set("type", params.type);
    if (params?.tag) q.set("tag", params.tag);
    if (params?.limit !== undefined) q.set("limit", String(params.limit));
    const qs = q.toString();
    return callApi<Inspiration[]>("GET", `/inspirations${qs ? `?${qs}` : ""}`);
  },
  get: (id: number) => callApi<Inspiration>("GET", `/inspirations/${id}`),
  /** Phase 6.1：详情（含关联 novel 的人物卡 / 大纲 / 章节摘要）。 */
  detail: (id: number) =>
    callApi<InspirationDetail>("GET", `/inspirations/${id}/detail`),
  create: (data: InspirationCreate) =>
    callApi<Inspiration>("POST", "/inspirations", data),
  update: (id: number, data: InspirationUpdate) =>
    callApi<Inspiration>("PATCH", `/inspirations/${id}`, data),
  remove: (id: number) => callApi<null>("DELETE", `/inspirations/${id}`),

  /** 批量删除（2026-10-29 素材库管理）：返回实际删除条数。 */
  batchDelete: (ids: number[]) =>
    callApi<InspirationBatchDeleteResult>("POST", "/inspirations/batch-delete", {
      ids,
    }),

  /** 按新顺序重排（2026-10-29 素材库管理）：ids 为拖拽后的显示顺序。 */
  reorder: (ids: number[]) =>
    callApi<InspirationReorderResult>("POST", "/inspirations/reorder", { ids }),

  /** 调 LLM 生成 n 个简要剧情版本（不入库，由前端决定是否保存）。 */
  generatePlot: (data: PlotGenerationRequest) =>
    callApi<PlotGenerationResponse>("POST", "/inspirations/generate-plot", data),

  /** 流式生成简要剧情（ndjson；前端按行解析）。 */
  generatePlotStream: (data: PlotGenerationRequest, signal?: AbortSignal): StreamRequest => ({
    url: "/inspirations/generate-plot/stream",
    method: "POST",
    body: data,
    signal,
  }),
};
