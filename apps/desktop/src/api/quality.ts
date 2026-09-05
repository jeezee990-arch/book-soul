import { callApi } from "./index";

export interface DimensionIssue {
  type: string;
  character: string;
  quote: string;
  problem: string;
  suggestion: string;
}

export interface DimensionResult {
  dimension: string;
  score: number;
  issues: DimensionIssue[];
  suggestions: string[];
  error: string | null;
}

export interface QualityReport {
  chapter_id: number;
  novel_id: number;
  chapter_title: string;
  genre: string;
  total_score: number;
  dimension_scores: Record<string, number>;
  dimension_results: DimensionResult[];
  issues: DimensionIssue[];
  suggestions: string[];
  provider: string;
  model: string;
}

export const qualityApi = {
  check: (novelId: number, chapterId: number) =>
    callApi<QualityReport>(
      "POST",
      `/novels/${novelId}/chapters/${chapterId}/quality`,
    ),
};
