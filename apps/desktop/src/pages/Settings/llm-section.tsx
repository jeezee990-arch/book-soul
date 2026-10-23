/**
 * 设置 · LLM 与密钥分区。
 *
 * 在原设置页基础上补了一个**「测试连接」**按钮 ——
 * 后端 POST /llm/test 一直就绪但前端没接，导致用户配完 key
 * 只能靠"生成一次看报不报错"来验证。
 */

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  settingsApi,
  llmApi,
  alignModel,
  type LLMProvider,
  type ProviderModels,
  type Settings,
  type ApiKeySource,
} from "@/api/settings";
import { ApiError } from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

const PROVIDERS: { value: LLMProvider; label: string }[] = [
  { value: "mimo", label: "mimo（主用，国内快）" },
  { value: "minimax", label: "minimax（备用）" },
  { value: "openai", label: "OpenAI（备用）" },
  { value: "ollama", label: "Ollama（本地）" },
];

const KEY_SOURCE_LABEL: Record<ApiKeySource, string> = {
  env: "环境变量",
  secret_store: "加密文件",
  keyring: "系统凭据",
  none: "未配置",
};

interface TestState {
  status: "idle" | "testing" | "ok" | "fail";
  message: string;
  detail?: string;
}

export default function LlmSection() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [llmProvider, setLlmProvider] = useState<LLMProvider>("mimo");
  const [llmModel, setLlmModel] = useState("");
  const [modelInfo, setModelInfo] = useState<ProviderModels | null>(null);
  const [modelsLoading, setModelsLoading] = useState(false);
  const modelInfoRef = useRef<ProviderModels | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [test, setTest] = useState<TestState>({ status: "idle", message: "" });

  const keySource: ApiKeySource = settings?.api_key_source?.[llmProvider] ?? "none";

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    settingsApi
      .get()
      .then((s) => {
        if (cancelled) return;
        setSettings(s);
        setLlmProvider(s.llm.provider);
        setLlmModel(() => alignModel(s.llm.model, modelInfoRef.current));
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          toast.error("加载设置失败", {
            description: e instanceof ApiError ? e.message : String(e),
          });
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // 换 provider → 实时拉模型列表
  useEffect(() => {
    let cancelled = false;
    setModelsLoading(true);
    llmApi
      .listModels(llmProvider)
      .then((info) => {
        if (cancelled) return;
        modelInfoRef.current = info;
        setModelInfo(info);
        setLlmModel((cur) => alignModel(cur, info));
      })
      .catch(() => {
        if (!cancelled) {
          modelInfoRef.current = null;
          setModelInfo(null);
        }
      })
      .finally(() => {
        if (!cancelled) setModelsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [llmProvider]);

  async function handleSaveLLM() {
    setSaving(true);
    try {
      const updated = await settingsApi.update({
        llm: { provider: llmProvider, model: llmModel },
      });
      setSettings(updated);
      toast.success("LLM 设置已保存", {
        description: `之后的生成都会走 ${updated.llm.provider} / ${updated.llm.model}`,
      });
    } catch (e: unknown) {
      toast.error("保存失败", {
        description: e instanceof ApiError ? e.message : String(e),
      });
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveApiKey() {
    if (!apiKey.trim()) {
      toast.error("请输入 API Key");
      return;
    }
    setSaving(true);
    try {
      const updated = await settingsApi.setApiKey(llmProvider, apiKey.trim());
      setSettings(updated);
      setApiKey("");
      toast.success(`${llmProvider} 的 API Key 已加密保存`, {
        description: "已用 Windows DPAPI 加密后写入数据目录，明文不落盘。",
      });
      if (updated.llm.provider !== llmProvider) {
        toast.warning(`当前生成仍走 ${updated.llm.provider}`, {
          description: `想用 ${llmProvider} 生成，请把上方 Provider 选成它再保存。`,
        });
      }
    } catch (e: unknown) {
      toast.error("保存失败", {
        description: e instanceof ApiError ? e.message : String(e),
      });
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteApiKey() {
    setSaving(true);
    try {
      const updated = await settingsApi.deleteApiKey(llmProvider);
      setSettings(updated);
      toast.success("已删除");
    } catch (e: unknown) {
      toast.error("删除失败", {
        description: e instanceof ApiError ? e.message : String(e),
      });
    } finally {
      setSaving(false);
    }
  }

  /** 真实调一次模型，验证连通性 */
  async function handleTest() {
    setTest({ status: "testing", message: "正在测试连接…" });
    const started = Date.now();
    try {
      const r = await llmApi.test({
        provider: llmProvider,
        prompt: "用一句话介绍你自己",
        max_tokens: 64,
      });
      const ms = Date.now() - started;
      setTest({
        status: "ok",
        message: "连接成功",
        detail: `${r.model} · 延迟 ${ms}ms · ${r.total_tokens} tokens`,
      });
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      setTest({ status: "fail", message: "连接失败", detail: msg });
    }
  }

  if (loading) {
    return <p className="text-[12px] text-neutral-400">加载中…</p>;
  }

  return (
    <div>
      <h3 className="text-[14px] font-semibold">LLM 与密钥</h3>
      <p className="mt-0.5 mb-4 text-[11.5px] leading-relaxed text-neutral-400">
        生成走哪个模型、用哪个 Key 都在这里。Key 用 Windows DPAPI
        加密后写入数据目录，明文永不落盘。
      </p>

      {/* Provider + Model */}
      <div className="mb-3 flex items-center gap-3">
        <span className="w-24 shrink-0 text-[12px] text-neutral-500">Provider</span>
        <Select
          value={llmProvider}
          onValueChange={(v) => setLlmProvider(v as LLMProvider)}
          disabled={saving}
        >
          <SelectTrigger className="w-56">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {PROVIDERS.map((p) => (
              <SelectItem key={p.value} value={p.value}>
                {p.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-3">
        <span className="w-24 shrink-0 text-[12px] text-neutral-500">模型</span>
        {modelInfo && modelInfo.models.length > 0 ? (
          <Select
            value={llmModel}
            onValueChange={setLlmModel}
            disabled={saving || modelsLoading}
          >
            <SelectTrigger className="w-72">
              <SelectValue placeholder="选择模型" />
            </SelectTrigger>
            <SelectContent>
              {modelInfo.models.map((m) => {
                // live_models 为空 = 没能拿到服务端清单（没配 Key / 401 / 没刷新）。
                // 这时"是否下线"无从判断，不能把所有模型都标成已下线。
                const offline =
                  modelInfo.live_models.length > 0 &&
                  !modelInfo.live_models.includes(m);
                return (
                  <SelectItem key={m} value={m}>
                    {m}
                    {offline ? "（服务端已下线）" : ""}
                  </SelectItem>
                );
              })}
            </SelectContent>
          </Select>
        ) : (
          <Input
            value={llmModel}
            onChange={(e) => setLlmModel(e.target.value)}
            disabled={saving}
            className="w-72"
            placeholder={modelsLoading ? "正在拉取模型列表…" : "模型名"}
          />
        )}
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setModelsLoading(true);
            llmApi
              .listModels(llmProvider)
              .then((info) => {
                modelInfoRef.current = info;
                setModelInfo(info);
                setLlmModel((cur) => alignModel(cur, info));
                toast.success("模型列表已刷新", { description: info.message });
              })
              .catch((e: unknown) =>
                toast.error("刷新失败", {
                  description: e instanceof ApiError ? e.message : String(e),
                }),
              )
              .finally(() => setModelsLoading(false));
          }}
          disabled={saving || modelsLoading}
        >
          刷新列表
        </Button>
      </div>

      {/* 没拿到服务端清单时说明原因，避免用户误以为所有模型都下线了 */}
      {modelInfo && modelInfo.live_models.length === 0 ? (
        <p className="mb-3 text-[11.5px] leading-relaxed text-neutral-400">
          未获取到服务端模型清单
          {modelInfo.message ? `（${modelInfo.message}）` : ""}
          ，暂时无法判断哪些模型已下线。配置 API Key 后点「刷新列表」重试。
        </p>
      ) : null}

      <p className="mb-3 text-[11.5px] text-neutral-400">
        当前生效：
        <b className="font-mono">{settings?.llm.provider}</b> /{" "}
        <b className="font-mono">{settings?.llm.model}</b>
        {llmProvider !== settings?.llm.provider ? (
          <span className="ml-2 text-amber-600 dark:text-amber-400">
            （上方改动尚未保存）
          </span>
        ) : null}
      </p>

      {modelInfo &&
      modelInfo.live_models.length > 0 &&
      llmModel &&
      !modelInfo.live_models.includes(llmModel) ? (
        <p className="mb-3 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-[11.5px] text-amber-700 dark:text-amber-300">
          ⚠️ 服务端当前不支持模型 <b>{llmModel}</b>，生成时会报错。
          请在上方下拉框里换一个可用模型（实时支持：
          {modelInfo.live_models.join("、")}）。
        </p>
      ) : null}

      <div className="mb-6 flex items-center gap-2.5">
        <Button onClick={() => void handleSaveLLM()} disabled={saving} size="sm">
          保存为当前生效
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => void handleTest()}
          disabled={test.status === "testing"}
        >
          {test.status === "testing" ? "测试中…" : "测试连接"}
        </Button>
      </div>

      {test.status !== "idle" ? (
        <div
          className={cn(
            "mb-6 flex items-center gap-2.5 rounded-lg border px-3 py-2.5 text-[11.5px]",
            test.status === "ok"
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300"
              : test.status === "fail"
                ? "border-rose-500/30 bg-rose-500/10 text-rose-600 dark:text-rose-300"
                : "border-neutral-200 bg-neutral-50 text-neutral-500 dark:border-neutral-800 dark:bg-neutral-800/40",
          )}
        >
          <span>{test.message}</span>
          {test.detail ? (
            <span className="ml-auto font-mono text-[10.5px] text-neutral-400">
              {test.detail}
            </span>
          ) : null}
        </div>
      ) : null}

      {/* API Key */}
      <div className="border-t border-neutral-200 pt-4 dark:border-neutral-800">
        <h4 className="mb-2 text-[12.5px] font-semibold">API Key</h4>
        {keySource === "env" ? (
          <p className="mb-3 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-[11.5px] text-amber-700 dark:text-amber-300">
            ⚠️ 当前 key 来自<b>环境变量</b>，而环境变量优先级最高 ——
            在这里保存新 key <b>不会生效</b>。请先清掉 .env
            里的对应那一行，再回来保存。
          </p>
        ) : null}

        <div className="mb-2 flex items-center gap-2.5">
          <span className="w-24 shrink-0 text-[12px] text-neutral-500">Provider</span>
          <span className="font-mono text-[12px]">{llmProvider}</span>
          {settings?.api_key_configured[llmProvider] ? (
            <span className="rounded border border-emerald-500/30 px-1.5 py-0.5 text-[10px] tracking-wider text-emerald-500 uppercase">
              已配置
            </span>
          ) : (
            <span className="rounded border border-neutral-200 px-1.5 py-0.5 text-[10px] tracking-wider text-neutral-400 uppercase dark:border-neutral-800">
              未配置
            </span>
          )}
          {keySource !== "none" ? (
            <span className="rounded border border-sky-500/30 px-1.5 py-0.5 text-[10px] tracking-wider text-sky-500 uppercase">
              来源：{KEY_SOURCE_LABEL[keySource]}
            </span>
          ) : null}
        </div>

        <div className="flex items-center gap-2.5">
          <span className="w-24 shrink-0 text-[12px] text-neutral-500">Key</span>
          <Input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            disabled={saving}
            className="w-96"
            placeholder="sk-..."
          />
          <Button
            onClick={() => void handleSaveApiKey()}
            disabled={saving || !apiKey.trim()}
            size="sm"
          >
            加密保存
          </Button>
          {settings?.api_key_configured[llmProvider] ? (
            <Button
              onClick={() => void handleDeleteApiKey()}
              disabled={saving}
              size="sm"
              variant="outline"
            >
              删除
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
