import { callApi } from "./index";
import type { StreamRequest } from "./streams";
import type { Outline } from "@/lib/types";

export type OutlineCreate = Omit<
  Outline,
  "id" | "created_at" | "updated_at"
>;

export type OutlineUpdate = Partial<Omit<OutlineCreate, "novel_id">>;

// ===== Phase 3.4：基于剧情生成大纲 =====

export interface OutlineGenerationRequest {
  genre: string;
  plot_summary: string;
  keywords?: string[];
  novel_name?: string;
  /**
   * 大纲模式：
   * - `complete`：完整大纲，从开头写到全书结束（适合短篇小说）
   * - `semi_open`：半开放式，只写前期并留悬念，后续作者自行创作或 AI 续写
   * - `freedom`：创作型，散文 + 关键节拍 + 主题
   */
  outline_type?: "complete" | "semi_open" | "freedom";
  user_extra?: string;
}

export interface OutlineGenerationResponse {
  novel_id: number;
  novel_name: string;
  outline_id: number;
  outline_type: string;
  structure: Record<string, unknown>;
  provider: string;
  model: string;
}

export const outlinesApi = {
  list: (novelId: number) =>
    callApi<Outline[]>("GET", `/novels/${novelId}/outlines`),
  create: (data: OutlineCreate) =>
    callApi<Outline>("POST", `/novels/${data.novel_id}/outlines`, data),
  update: (id: number, novelId: number, data: OutlineUpdate) =>
    callApi<Outline>("PATCH", `/novels/${novelId}/outlines/${id}`, data),
  remove: (id: number, novelId: number) =>
    callApi<null>("DELETE", `/novels/${novelId}/outlines/${id}`),

  /** Phase 3.4：基于 plot 自动建 novel + 调 LLM + 入库。 */
  generate: (data: OutlineGenerationRequest) =>
    callApi<OutlineGenerationResponse>(
      "POST",
      "/novels/outlines/generate",
      data,
    ),

  /** 流式大纲生成（ndjson；前端按行解析）。 */
  generateStream: (data: OutlineGenerationRequest, signal?: AbortSignal): StreamRequest => ({
    url: "/novels/outlines/generate/stream",
    method: "POST",
    body: data,
    signal,
  }),
};
