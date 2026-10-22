import { useEffect } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { useUIStore } from "@/stores/uiStore";

interface NavItem {
  to: string;
  label: string;
  end?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "灵感园", end: true },
  { to: "/creation", label: "创作" },
  { to: "/quality", label: "质检" },
  { to: "/library", label: "作品库" },
  { to: "/skills", label: "Skills" },
  { to: "/settings", label: "设置" },
];

/**
 * 顶栏 + 左侧细边栏 + 主区
 * - 主题由 uiStore.theme 决定（默认 dark）
 * - 灰阶 + indigo 单一强调色
 * - 当前路由用浅灰底 + 细左侧边线
 */
export default function Layout() {
  const theme = useUIStore((s) => s.theme);

  useEffect(() => {
    if (theme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [theme]);

  return (
    <div className="h-screen flex flex-col bg-neutral-50 dark:bg-neutral-950 text-neutral-900 dark:text-neutral-100 antialiased">
      {/* Top bar */}
      <header className="h-12 shrink-0 flex items-center px-5 border-b border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-indigo-500" aria-hidden />
          <span className="text-sm font-semibold tracking-tight">Book Soul</span>
          <span className="text-xs text-neutral-400 dark:text-neutral-500 ml-2">
            网文 AI 写作
          </span>
        </div>
      </header>

      {/* Sidebar + Main */}
      <div className="flex-1 flex min-h-0">
        <aside className="w-48 shrink-0 border-r border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900">
          <nav className="py-3 px-2 space-y-0.5">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  [
                    "block px-3 py-1.5 text-sm rounded-md transition-colors",
                    isActive
                      ? "bg-neutral-100 dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100 font-medium"
                      : "text-neutral-500 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-100 hover:bg-neutral-50 dark:hover:bg-neutral-800/50",
                  ].join(" ")
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </aside>

        <main className="flex-1 min-w-0 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-8 py-10 pb-32">
            <Outlet />
          </div>
        </main>
      </div>

      <Toaster position="bottom-right" theme="dark" richColors closeButton />
    </div>
  );
}
