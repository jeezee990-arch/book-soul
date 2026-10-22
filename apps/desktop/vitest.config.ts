import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

/**
 * 前端测试配置。
 *
 * 为什么单独一个文件而不是塞进 vite.config.ts？
 * ----------------------------------------------------
 * Vite 的配置是"打包"用的，vitest 的配置是"跑测试"用的，两者关注点不同
 * （比如 test.environment、覆盖率 provider）。
 * vitest 会优先读 vitest.config.*，不会和 vite.config.ts 打架。
 *
 * 目前只覆盖**纯逻辑**（流式解析、URL 拼接这类），用 node 环境即可，
 * 不引入 jsdom —— 测试要快、要稳，不要为了跑得快引入一堆 DOM 依赖。
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    reporters: "default",
    // 单个测试文件超时 10 秒（网络类 mock 不应该更慢）
    testTimeout: 10_000,
  },
});
