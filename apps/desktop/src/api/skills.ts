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

export interface SkillStatus extends SkillSummary {
  source: "builtin" | "user";
  enabled: boolean;
  apply_type: "post_process" | "pre_process" | "both";
  triggers: string[];
}

export interface SkillRunResult {
  success: boolean;
  data: Record<string, unknown>;
  error: string | null;
}

export const skillsApi = {
  list: () => callApi<SkillStatus[]>("GET", "/skills"),
  enable: (name: string) => callApi<SkillStatus>("POST", `/skills/${name}/enable`),
  disable: (name: string) =>
    callApi<SkillStatus>("POST", `/skills/${name}/disable`),
  listForScene: (scene: string) =>
    callApi<string[]>("GET", `/skills/scene/${scene}`),
  /** debug：手动触发（一般场景下 skill 自动调用，不需要此接口） */
  run: (name: string, payload: Record<string, unknown>) =>
    callApi<SkillRunResult>("POST", `/skills/${name}/run`, payload),
};