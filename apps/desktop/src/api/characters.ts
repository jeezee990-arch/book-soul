import { callApi } from "./index";
import type { Character } from "@/lib/types";

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
  is_active?: boolean;
};

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
};
