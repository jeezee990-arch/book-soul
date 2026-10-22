import { useEffect, useState } from "react";
import { toast } from "sonner";
import { settingsApi, type Settings, type LLMProvider, type UITheme, type ApiKeySource } from "@/api/settings";
import { ApiError } from "@/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import LoadingSkeleton from "@/components/layout/LoadingSkeleton";
import ErrorState from "@/components/layout/ErrorState";
import BackupPanel from "@/components/BackupPanel";

const PROVIDERS: { value: LLMProvider; label: string }[] = [
  { value: "mimo", label: "mimo（主用，国内快）" },
  { value: "minimax", label: "minimax（备用，需 VPN）" },
  { value: "openai", label: "OpenAI（备用）" },
  { value: "ollama", label: "Ollama（本地）" },
];

const THEMES: { value: UITheme; label: string }[] = [
  { value: "dark", label: "深色" },
  { value: "light", label: "浅色" },
];

/** API Key 来源标签 */
const KEY_SOURCE_LABEL: Record<ApiKeySource, string> = {
  env: "环境变量",
  secret_store: "加密文件",
  keyring: "系统凭据",
  none: "未配置",
};

/** 设置 —— LLM Provider / API Key / 数据目录 / 主题 / 加密 */
export default function Settings() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // LLM 字段临时值
  const [llmProvider, setLlmProvider] = useState<LLMProvider>("mimo");
  const [llmModel, setLlmModel] = useState("mimo-v2.5-pro");
  // API Key 临时值（每次保存后清空）
  const [apiKey, setApiKey] = useState("");
  // 主题
  const [theme, setTheme] = useState<UITheme>("dark");
  // 加密
  const [encryption, setEncryption] = useState(false);
  // 当前 provider 的 key 来源
  const keySource: ApiKeySource = settings?.api_key_source?.[llmProvider] ?? "none";

  // 加载
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    settingsApi
      .get()
      .then((s) => {
        if (!cancelled) {
          setSettings(s);
          setLlmProvider(s.llm.provider);
          setLlmModel(s.llm.model);
          setTheme(s.ui.theme);
          setEncryption(s.security.encryption_enabled);
        }
      })
      .catch((e: unknown) => {
        const msg = e instanceof ApiError ? e.message : String(e);
        if (!cancelled) {
          setError(msg);
          toast.error("加载设置失败", { description: msg });
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // theme 即时切换（不动 settings 持久化状态）
  useEffect(() => {
    if (theme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [theme]);

  // ===== Handlers =====
  const handleSaveLLM = async () => {
    setSaving(true);
    try {
      const updated = await settingsApi.update({
        llm: { provider: llmProvider, model: llmModel },
      });
      setSettings(updated);
      toast.success("LLM 设置已保存");
    } catch (e) {
      toast.error("保存失败", {
        description: e instanceof ApiError ? e.message : String(e),
      });
    } finally {
      setSaving(false);
    }
  };

  const handleSaveApiKey = async () => {
    if (!apiKey.trim()) {
      toast.error("请输入 API Key");
      return;
    }
    setSaving(true);
    try {
      const updated = await settingsApi.setApiKey(llmProvider, apiKey.trim());
      setSettings(updated);
      setApiKey("");
      toast.success(`${llmProvider} 的 API Key 已保存到 Keyring`);
    } catch (e) {
      toast.error("保存失败", {
        description: e instanceof ApiError ? e.message : String(e),
      });
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteApiKey = async () => {
    setSaving(true);
    try {
      const updated = await settingsApi.deleteApiKey(llmProvider);
      setSettings(updated);
      toast.success("已删除");
    } catch (e) {
      toast.error("删除失败", {
        description: e instanceof ApiError ? e.message : String(e),
      });
    } finally {
      setSaving(false);
    }
  };

  const handleSaveUI = async () => {
    setSaving(true);
    try {
      const updated = await settingsApi.update({ ui: { theme } });
      setSettings(updated);
      toast.success("主题已保存");
    } catch (e) {
      toast.error("保存失败", {
        description: e instanceof ApiError ? e.message : String(e),
      });
    } finally {
      setSaving(false);
    }
  };

  const handleSaveSecurity = async () => {
    setSaving(true);
    try {
      const updated = await settingsApi.update({
        security: { encryption_enabled: encryption },
      });
      setSettings(updated);
      toast.success("已保存", {
        description: "加密开关需要重启服务后生效。",
      });
    } catch (e) {
      toast.error("保存失败", {
        description: e instanceof ApiError ? e.message : String(e),
      });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <LoadingSkeleton rows={3} height={120} />;
  }

  if (error) {
    return <ErrorState message={error} />;
  }

  return (
    <section className="space-y-6">
      <header className="space-y-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">设置</h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400">
          LLM Provider · API Key · 数据目录 · 主题 · 加密开关。
        </p>
      </header>

      {/* LLM Provider + Model */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">LLM Provider</CardTitle>
          <CardDescription>选择当前使用的 LLM 与模型名。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-sm text-neutral-500 w-20">Provider</span>
            <Select
              value={llmProvider}
              onValueChange={(v) => setLlmProvider(v as LLMProvider)}
              disabled={saving}
            >
              <SelectTrigger className="w-48">
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
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-sm text-neutral-500 w-20">Model</span>
            <Input
              value={llmModel}
              onChange={(e) => setLlmModel(e.target.value)}
              disabled={saving}
              className="w-64"
              placeholder="mimo-v2.5-pro"
            />
          </div>
          <Button onClick={handleSaveLLM} disabled={saving} size="sm">
            保存
          </Button>
        </CardContent>
      </Card>

      {/* API Key */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">API Key</CardTitle>
          <CardDescription>
            优先使用环境变量（.env）；在此页保存则用 Windows DPAPI 加密后存进
            应用数据目录（明文不落盘）。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-sm text-neutral-500 w-20">Provider</span>
            <span className="text-sm font-mono">{llmProvider}</span>
            {settings?.api_key_configured[llmProvider] ? (
              <span className="text-[10px] uppercase tracking-wider text-emerald-500 border border-emerald-500/30 rounded px-1.5 py-0.5">
                已配置
              </span>
            ) : (
              <span className="text-[10px] uppercase tracking-wider text-neutral-400 border border-neutral-200 dark:border-neutral-800 rounded px-1.5 py-0.5">
                未配置
              </span>
            )}
            {keySource !== "none" && (
              <span className="text-[10px] uppercase tracking-wider text-sky-500 border border-sky-500/30 rounded px-1.5 py-0.5">
                来源：{KEY_SOURCE_LABEL[keySource]}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-sm text-neutral-500 w-20">Key</span>
            <Input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              disabled={saving}
              className="w-96"
              placeholder="sk-..."
            />
            <Button
              onClick={handleSaveApiKey}
              disabled={saving || !apiKey.trim()}
              size="sm"
            >
              保存到 Keyring
            </Button>
            {settings?.api_key_configured[llmProvider] && (
              <Button
                onClick={handleDeleteApiKey}
                disabled={saving}
                size="sm"
                variant="outline"
              >
                删除
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* 数据目录（只读 + 提示） */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">数据目录</CardTitle>
          <CardDescription>
            由环境变量 <code className="font-mono text-xs">BOOK_SOUL_DATA_DIR</code> 决定（默认{" "}
            <code className="font-mono text-xs">~/Documents/BookSoul</code>）。
            修改后重启服务生效。
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-neutral-500 dark:text-neutral-400">
            路径由启动时的环境变量决定；Phase 3 接入 UI 修改。
          </p>
        </CardContent>
      </Card>

      {/* 备份 / 恢复（Phase 7.4） */}
      <BackupPanel />

      {/* 主题 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">主题</CardTitle>
          <CardDescription>立即生效，保存到 settings.yaml。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-3">
            <span className="text-sm text-neutral-500 w-20">主题</span>
            <Select
              value={theme}
              onValueChange={(v) => setTheme(v as UITheme)}
              disabled={saving}
            >
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {THEMES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button onClick={handleSaveUI} disabled={saving} size="sm">
            保存
          </Button>
        </CardContent>
      </Card>

      {/* 加密开关 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">加密</CardTitle>
          <CardDescription>
            启用 Fernet 加密敏感字段（key 自动生成并存入 Keyring）。改后需重启服务。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="encryption"
              checked={encryption}
              onChange={(e) => setEncryption(e.target.checked)}
              disabled={saving}
              className="rounded border-neutral-300"
            />
            <label htmlFor="encryption" className="text-sm">
              启用 Fernet 加密
            </label>
          </div>
          <Button onClick={handleSaveSecurity} disabled={saving} size="sm">
            保存
          </Button>
        </CardContent>
      </Card>
    </section>
  );
}
