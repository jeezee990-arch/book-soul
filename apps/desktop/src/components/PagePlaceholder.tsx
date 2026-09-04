interface PagePlaceholderProps {
  title: string;
  description: string;
  status?: string;
}

/**
 * 5 个页面的占位卡片 —— 简洁卡片风格
 * 极简：标题 + 一行描述 + 状态徽章，不堆色彩
 */
export default function PagePlaceholder({
  title,
  description,
  status = "开发中",
}: PagePlaceholderProps) {
  return (
    <section className="space-y-6">
      <header className="space-y-1.5">
        <div className="flex items-center gap-2.5">
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          <span className="text-[10px] uppercase tracking-wider text-neutral-400 dark:text-neutral-500 border border-neutral-200 dark:border-neutral-800 rounded px-1.5 py-0.5">
            {status}
          </span>
        </div>
        <p className="text-sm text-neutral-500 dark:text-neutral-400">
          {description}
        </p>
      </header>

      <div className="border border-dashed border-neutral-300 dark:border-neutral-800 rounded-lg p-12 text-center">
        <p className="text-sm text-neutral-400 dark:text-neutral-500">
          即将上线
        </p>
      </div>
    </section>
  );
}
