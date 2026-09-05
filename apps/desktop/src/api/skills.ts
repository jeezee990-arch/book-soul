import { callApi } from "./index";

export interface SkillSummary {
  name: string;
  description: string;
  input_schema: {
    type: string;
    properties: Record<string, unknown>;
    required?: string[];
  };
  requires_llm: boolean;
}

export interface SkillRunResult {
  success: boolean;
  data: Record<string, unknown>;
  error: string | null;
}

export const skillsApi = {
  list: () => callApi<SkillSummary[]>("GET", "/skills"),
  run: (name: string, payload: Record<string, unknown>) =>
    callApi<SkillRunResult>("POST", `/skills/${name}/run`, payload),
};
