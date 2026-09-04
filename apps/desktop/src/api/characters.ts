import { callApi } from "./index";
import type {
  Character,
  CharacterGrowthEvent,
  CharacterVersion,
} from "@/lib/types";

export type CharacterCreate = Omit<
  Character,
  | "id"
  | "created_at"
  | "updated_at"
  | "current_version_id"
  | "growth_arc"
  | "is_active"
> & { is_active?: boolean };

export type CharacterUpdate = Partial<Omit<CharacterCreate, "novel_id">> & {
  growth_arc?: string | null;
  is_active?: boolean;
};

/** Phase 3.5：从大纲自动生成 */
export interface CharacterGenerationRequest {
  outline: Record<string, unknown>;
  genre?: string;
}

export interface CharacterGenerationResponse {
  novel_id: number;
  characters: Character[];
  provider: string;
  model: string;
}

export const charactersApi = {
  list: (novelId: number, params?: { role?: string; is_active?: boolean }) => {
    const q = new URLSearchParams();
    if (params?.role) q.set("role", params.role);
    if (params?.is_active !== undefined)
      q.set("is_active", String(params.is_active));
    const qs = q.toString();
    return callApi<Character[]>(
      "GET",
      `/novels/${novelId}/characters${qs ? `?${qs}` : ""}`,
    );
  },
  get: (id: number) => callApi<Character>("GET", `/characters/${id}`),
  create: (data: CharacterCreate) =>
    callApi<Character>("POST", `/novels/${data.novel_id}/characters`, data),
  update: (id: number, data: CharacterUpdate) =>
    callApi<Character>("PATCH", `/characters/${id}`, data),
  remove: (id: number) => callApi<null>("DELETE", `/characters/${id}`),
  /** Phase 3.5：从大纲自动生成（两阶段 LLM） */
  generateFromOutline: (
    novelId: number,
    data: CharacterGenerationRequest,
  ) =>
    callApi<CharacterGenerationResponse>(
      "POST",
      `/novels/${novelId}/characters/generate-from-outline`,
      data,
    ),
  /** 记录一次性格/状态变化（自动追加 growth_arc + 新版本） */
  recordGrowth: (id: number, data: CharacterGrowthEvent) =>
    callApi<CharacterVersion>("POST", `/characters/${id}/growth`, data),
  /** 查看人物卡版本历史 */
  listVersions: (id: number) =>
    callApi<CharacterVersion[]>("GET", `/characters/${id}/versions`),
};
