import { callApi } from "./index";
import type { Novel } from "@/lib/types";

export type NovelCreate = Omit<
  Novel,
  "id" | "created_at" | "updated_at" | "current_version_id" | "word_count" | "growth_arc" | "is_active" | "novel_id"
> & {
  // 实际创建只需要必填字段，其他可选
};

export type NovelUpdate = Partial<NovelCreate>;

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
};
