import { callApi } from "./index";
import type { Inspiration } from "@/lib/types";

export type InspirationCreate = Omit<
  Inspiration,
  "id" | "created_at"
>;

export type InspirationUpdate = Partial<Omit<InspirationCreate, "novel_id">>;

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
  create: (data: InspirationCreate) =>
    callApi<Inspiration>("POST", "/inspirations", data),
  update: (id: number, data: InspirationUpdate) =>
    callApi<Inspiration>("PATCH", `/inspirations/${id}`, data),
  remove: (id: number) => callApi<null>("DELETE", `/inspirations/${id}`),
};
