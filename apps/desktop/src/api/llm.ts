/**
 * LLM 调用的前端封装。
 *
 * 端到端路径：invoke("test_llm") → Rust 调 Python /llm/test → Python 调真实 LLM
 */

import { invoke } from "@tauri-apps/api/core";

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
