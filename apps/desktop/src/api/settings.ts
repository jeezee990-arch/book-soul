import { callApi } from "./index";

export type LLMProvider = "mimo" | "minimax" | "openai" | "ollama";
export type UITheme = "dark" | "light";

export interface LLMConfig {
  provider: LLMProvider;
  model: string;
}

export interface UIConfig {
  theme: UITheme;
}

export interface SecurityConfig {
  encryption_enabled: boolean;
}

export interface Settings {
  llm: LLMConfig;
  ui: UIConfig;
  security: SecurityConfig;
  /** 各 provider 是否已存 API key（key 值永不返回） */
  api_key_configured: Record<LLMProvider, boolean>;
  /**
   * 各 provider 的 key 来源：
   * env（环境变量）/ secret_store（DPAPI 加密文件）/ keyring（系统凭据）/ none
   */
  api_key_source: Record<LLMProvider, ApiKeySource>;
}

export type ApiKeySource = "env" | "secret_store" | "keyring" | "none";

/** 各 provider 的健康状态（/llm/health） */
export type ProviderHealth = Record<
  LLMProvider,
  { ok: boolean; message: string }
>;

export type SettingsUpdate = Partial<{
  llm: LLMConfig;
  ui: UIConfig;
  security: SecurityConfig;
}>;

/**
 * 某个 provider 的模型清单（GET /llm/models）。
 *
 * models —— 实时列表 ∪ 配置登记列表（下拉框用这个）
 * live_models —— 服务端此刻真实支持的
 * configured_models —— config/llm.yaml 里登记的
 */
export interface ProviderModels {
  provider: LLMProvider;
  models: string[];
  live_models: string[];
  configured_models: string[];
  default_model: string;
  reachable: boolean;
  message: string;
}

export const settingsApi = {
  get: () => callApi<Settings>("GET", "/settings"),
  update: (data: SettingsUpdate) => callApi<Settings>("PUT", "/settings", data),
  setApiKey: (provider: LLMProvider, key: string) =>
    callApi<Settings>("POST", `/settings/api-key/${provider}`, { key }),
  deleteApiKey: (provider: LLMProvider) =>
    callApi<Settings>("DELETE", `/settings/api-key/${provider}`),
};

/** LLM 相关端点（模型清单等） */
export const llmApi = {
  /** 实时拉取 provider 支持的模型列表（设置页下拉框） */
  listModels: (provider: LLMProvider) =>
    callApi<ProviderModels>("GET", `/llm/models?provider=${provider}`),
};
