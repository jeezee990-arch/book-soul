import { callApi } from "./index";
import type { Outline } from "@/lib/types";

export type OutlineCreate = Omit<
  Outline,
  "id" | "created_at" | "updated_at"
>;

export type OutlineUpdate = Partial<Omit<OutlineCreate, "novel_id">>;

export const outlinesApi = {
  list: (novelId: number) =>
    callApi<Outline[]>("GET", `/novels/${novelId}/outlines`),
  create: (data: OutlineCreate) =>
    callApi<Outline>("POST", `/novels/${data.novel_id}/outlines`, data),
  update: (id: number, novelId: number, data: OutlineUpdate) =>
    callApi<Outline>("PATCH", `/novels/${novelId}/outlines/${id}`, data),
  remove: (id: number, novelId: number) =>
    callApi<null>("DELETE", `/novels/${novelId}/outlines/${id}`),
};
