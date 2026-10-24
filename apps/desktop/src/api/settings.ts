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
  /** 当前数据目录的绝对路径（只读） */
  data_dir: string;
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

/**
 * 把当前选中的模型名"对齐"到服务端实际支持的列表。
 *
 * 为什么要这一步：服务端会下线模型（mimo 的 mimo-v2.5-pro 就是这么消失的），
 * 配置里留着一个服务端不认的模型名 → 生成时直接 400。
 * 对齐到默认模型 = 自动自愈，不用用户自己去猜该用哪个。
 */
export function alignModel(current: string, info: ProviderModels | null): string {
  if (!info || info.models.length === 0) return current;
  if (current && info.models.includes(current)) return current;
  return info.default_model || info.models[0] || current;
}

export const settingsApi = {
  get: () => callApi<Settings>("GET", "/settings"),
  update: (data: SettingsUpdate) => callApi<Settings>("PUT", "/settings", data),
  setApiKey: (provider: LLMProvider, key: string) =>
    callApi<Settings>("POST", `/settings/api-key/${provider}`, { key }),
  deleteApiKey: (provider: LLMProvider) =>
    callApi<Settings>("DELETE", `/settings/api-key/${provider}`),
};

/** LLM 测试端点（POST /llm/test）的响应。 */
export interface LLMTestResult {
  provider: string;
  model: string;
  content: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

/** LLM 相关端点（模型清单、探活、连通性测试） */
export const llmApi = {
  /**
   * 取 provider 支持的模型列表（设置页下拉框）。
   *
   * @param refresh true = 绕过服务端缓存强制重新拉取（「刷新列表」按钮用）。
   *   不带这个参数时走缓存 —— 实时拉取在网络差时要等好几秒，
   *   而设置页每次打开都会调一次。
   */
  listModels: (provider: LLMProvider, refresh = false) =>
    callApi<ProviderModels>(
      "GET",
      `/llm/models?provider=${provider}${refresh ? "&refresh=true" : ""}`,
    ),
  /**
   * 探活 provider（顶栏模型灯用）。
   *
   * @param provider 只探这一个。灯只关心"当前生效的那个 provider" ——
   *   如果每次都探全部，"用户用 mimo 但没配的 openai 不可达"会让灯白等 3 秒。
   *   不传则探全部。
   */
  health: (provider?: LLMProvider) =>
    callApi<ProviderHealth>(
      "GET",
      provider ? `/llm/health?provider=${provider}` : "/llm/health",
    ),
  /** 真实调一次模型验证连通性（设置页「测试连接」按钮） */
  test: (data?: { prompt?: string; provider?: string; max_tokens?: number }) =>
    callApi<LLMTestResult>("POST", "/llm/test", data ?? {}),
};
