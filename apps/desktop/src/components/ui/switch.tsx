/**
 * 开关组件（手写，未引入 @radix-ui/react-switch）。
 *
 * 为什么手写：本项目只在这一处需要开关，为此多拉一个 Radix 依赖不划算；
 * 交互语义（button + role="switch" + aria-checked）保持标准。
 */

import { cn } from "@/lib/utils";

export interface SwitchProps {
  /** 当前是否开启 */
  checked: boolean;
  /** 点击时回调目标状态 */
  onCheckedChange: (checked: boolean) => void;
  /** 禁用 */
  disabled?: boolean;
  /** 无障碍标签 */
  "aria-label"?: string;
  className?: string;
}

/** 小尺寸开关（34×19），用于设置页与右栏面板。 */
export function Switch({
  checked,
  onCheckedChange,
  disabled = false,
  className,
  ...rest
}: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        "relative h-[19px] w-[34px] shrink-0 rounded-full transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        checked ? "bg-indigo-500" : "bg-neutral-300 dark:bg-neutral-700",
        disabled && "cursor-not-allowed opacity-50",
        className,
      )}
      {...rest}
    >
      <span
        className={cn(
          "absolute top-[2px] left-[2px] h-[15px] w-[15px] rounded-full bg-white shadow transition-transform",
          checked && "translate-x-[15px]",
        )}
      />
    </button>
  );
}

export default Switch;
