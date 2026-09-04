import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

/** 设置 —— Phase 2.4 接入 LLM Provider / API Key / 数据目录 / 加密 */
export default function Settings() {
  return (
    <section className="space-y-6">
      <header className="space-y-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">设置</h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400">
          LLM Provider · API Key · 数据目录 · 主题 · 加密开关。
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">即将上线</CardTitle>
          <CardDescription>模块 2.4 接入。</CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-neutral-500 dark:text-neutral-400">
          计划提供：Provider 选择、API Key（系统 Keyring）、数据目录、主题切换、加密开关。
        </CardContent>
      </Card>
    </section>
  );
}
