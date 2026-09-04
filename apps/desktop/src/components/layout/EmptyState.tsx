/**
 * 空状态组件（Phase 3.9）。
 *
 * 用途：列表/页面无数据时显示（统一风格）。
 * 用法：<EmptyState title="..." description="..." icon="..." />
 */
import { type ReactNode } from "react";
import { Button } from "@/components/ui/button";

export interface EmptyStateProps {
  title: string;
  description?: string;
  /** emoji 或文本（避免引外部图标库，保持 Phase 3.9 静态） */
  icon?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  children?: ReactNode;
}

export default function EmptyState({
  title,
  description,
  icon,
  action,
  children,
}: EmptyStateProps) {
  return (
    <div className="border border-dashed border-neutral-300 dark:border-neutral-800 rounded-lg p-12 text-center space-y-3">
      {icon && (
        <div className="text-3xl" aria-hidden>
          {icon}
        </div>
      )}
      <div className="space-y-1">
        <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
          {title}
        </p>
        {description && (
          <p className="text-xs text-neutral-500 dark:text-neutral-400 max-w-md mx-auto">
            {description}
          </p>
        )}
      </div>
      {action && (
        <Button onClick={action.onClick} variant="outline" size="sm">
          {action.label}
        </Button>
      )}
      {children}
    </div>
  );
}
