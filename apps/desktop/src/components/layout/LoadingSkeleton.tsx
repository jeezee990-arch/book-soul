/**
 * 加载骨架屏（Phase 3.9）。
 *
 * 用途：列表/详情加载中显示（占位结构，避免白屏闪烁）。
 * 默认 3 行；可用 rows 改。
 */
interface Props {
  rows?: number;
  /** 整体高度（默认 80px） */
  height?: number;
  /** 容器 className */
  className?: string;
}

export default function LoadingSkeleton({
  rows = 3,
  height = 80,
  className = "",
}: Props) {
  return (
    <div className={`space-y-2 ${className}`} aria-busy aria-live="polite">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="rounded-md border border-neutral-200 dark:border-neutral-800 bg-neutral-100/50 dark:bg-neutral-900/50 animate-pulse"
          style={{ height: `${height}px` }}
        />
      ))}
    </div>
  );
}
