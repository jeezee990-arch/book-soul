import { callApi } from "./index";

export type LLMProvider = "minimax" | "openai" | "ollama";
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
}

export type SettingsUpdate = Partial<{
  llm: LLMConfig;
  ui: UIConfig;
  security: SecurityConfig;
}>;

export const settingsApi = {
  get: () => callApi<Settings>("GET", "/settings"),
  update: (data: SettingsUpdate) => callApi<Settings>("PUT", "/settings", data),
  setApiKey: (provider: LLMProvider, key: string) =>
    callApi<Settings>("POST", `/settings/api-key/${provider}`, { key }),
  deleteApiKey: (provider: LLMProvider) =>
    callApi<Settings>("DELETE", `/settings/api-key/${provider}`),
};
