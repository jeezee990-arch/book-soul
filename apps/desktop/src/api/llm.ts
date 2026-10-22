/**
 * LLM 调用的前端封装。
 *
 * 端到端路径：invoke("test_llm") → Rust 调 Python /llm/test → Python 调真实 LLM
 */

import { invoke } from "@tauri-apps/api/core";
import { callApi } from "./index";

export interface LlmTestRequest {
  prompt?: string;
  provider?: string;
  max_tokens?: number;
  system?: string;
}

export interface LlmTestResponse {
  provider: string;
  model: string;
  content: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

/**
 * 调用 Rust 端 test_llm 命令。
 * @throws Error 当后端不通、LLM 调用失败时
 */
export async function testLlm(req: LlmTestRequest = {}): Promise<LlmTestResponse> {
  return invoke<LlmTestResponse>("test_llm", {
    prompt: req.prompt ?? "用一句话介绍你自己",
    provider: req.provider ?? null,
    maxTokens: req.max_tokens ?? 200,
    system: req.system ?? null,
  });
}

/** 各 provider 的健康状态 */
export type ProviderHealthMap = Record<
  string,
  { ok: boolean; message: string }
>;

/**
 * 探活所有 provider（走普通 API 代理 → Python /llm/health）。
 *
 * 用途：设置页显示"云端模型可达 / 本地 Ollama 未启动"这类可操作提示，
 * 免得用户等 30 秒超时后只看到一个裸 ConnectError。
 */
export async function getProviderHealth(): Promise<ProviderHealthMap> {
  return callApi<ProviderHealthMap>("GET", "/llm/health");
}
