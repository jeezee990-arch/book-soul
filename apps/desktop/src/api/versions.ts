import { callApi } from "./index";
import type { ChapterVersion } from "@/lib/types";

export interface DiffStats {
  added: number;
  removed: number;
}

export interface DiffResponse {
  chapter_id: number;
  from_version_id: number | null;
  to_version_id: number;
  diff: string;
  stats: DiffStats;
}

export interface RollbackResponse {
  new_version: ChapterVersion;
  rolled_back_to: number;
}

export const versionsApi = {
  diff: (chapterId: number, versionId: number, otherId?: number) => {
    const qs = otherId !== undefined ? `?other_id=${otherId}` : "";
    return callApi<DiffResponse>(
      "GET",
      `/chapters/${chapterId}/versions/${versionId}/diff${qs}`,
    );
  },
  rollback: (chapterId: number, versionId: number) =>
    callApi<RollbackResponse>(
      "POST",
      `/chapters/${chapterId}/versions/${versionId}/rollback`,
    ),
};
