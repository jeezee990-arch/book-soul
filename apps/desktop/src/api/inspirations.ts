import { callApi } from "./index";
import type { Inspiration } from "@/lib/types";

export type InspirationCreate = Omit<
  Inspiration,
  "id" | "created_at"
>;

export type InspirationUpdate = Partial<Omit<InspirationCreate, "novel_id">>;

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
  novel: NovelContextSummary | null;
}

export const inspirationsApi = {
  list: (params?: { novel_id?: number; type?: string; tag?: string }) => {
    const q = new URLSearchParams();
    if (params?.novel_id !== undefined)
      q.set("novel_id", String(params.novel_id));
    if (params?.type) q.set("type", params.type);
    if (params?.tag) q.set("tag", params.tag);
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

  /** 调 LLM 生成 n 个简要剧情版本（不入库，由前端决定是否保存）。 */
  generatePlot: (data: PlotGenerationRequest) =>
    callApi<PlotGenerationResponse>("POST", "/inspirations/generate-plot", data),
};
