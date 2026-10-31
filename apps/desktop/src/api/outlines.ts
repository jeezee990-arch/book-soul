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
   * 要复用哪本书（2026-10-30 新增）。
   *
   * ⚠️ 靠 id 而不是名字区分"重生成同一本"和"新建一本"：
   * 名字会撞车 —— 素材库里已经有一本同名书时，新书会被合并进旧书
   * （旧书大纲被冲掉，新书存不进素材库）。
   * 不传 = 新建一本（后端保证名字唯一）。
   */
  novel_id?: number;
  /**
   * 大纲模式：
   * - `complete`：完整大纲，从开头写到全书结束（适合短篇小说）
   * - `semi_open`：半开放式，只写前期并留悬念，后续作者自行创作或 AI 续写
   * - `freedom`：创作型，散文 + 关键节拍 + 主题
   */
  outline_type?: "complete" | "semi_open" | "freedom";
  user_extra?: string;
  /**
   * 规模参数（2026-10-25 新增）。
   *
   * ⚠️ 以前规模写死在 prompt 里（20-40 章），作者写的"100 章"被无视。
   * 现在这三个数是**硬指标**，后端会写进 prompt 要求模型照做。
   */
  total_chapters?: number;
  chapters_per_volume?: number;
  words_per_chapter?: number;
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

/** AI 辅助续写大纲的请求（2026-10-25 新增）。 */
export interface OutlineContinueRequest {
  /** 新增几卷（1-5） */
  volume_count?: number;
  /** 每卷章数；缺省取已有大纲的平均值 */
  chapters_per_volume?: number;
  words_per_chapter?: number;
  keywords?: string[];
  user_extra?: string;
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

  /**
   * 流式**续写**大纲（ndjson）。
   *
   * 基于已有大纲 + 已写章节，生成后续卷章并**追加**到原大纲末尾。
   */
  continueStream: (
    novelId: number,
    outlineId: number,
    data: OutlineContinueRequest,
    signal?: AbortSignal,
  ): StreamRequest => ({
    url: `/novels/${novelId}/outlines/${outlineId}/continue/stream`,
    method: "POST",
    body: data,
    signal,
  }),
};
