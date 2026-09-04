import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// 此文件由 Vite 加载，vite.config.js 是 tsc emit 产物（Vite 优先 .js）。
// 改这里 + 同步改 vite.config.js；或修 tsconfig.node.json 加 noEmit:true 后删 .js。

// Tauri 推荐的 Vite 配置：
// - 固定端口 5173（与 tauri.conf.json 的 devUrl 一致）
// - 关闭 HMR overlay 强制清屏以避免 macOS 焦点问题
// - 显式 clearScreen=false 让 Tauri 自己控制
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  clearScreen: false,
  server: {
    port: 5173,
    strictPort: true,
    host: "127.0.0.1",
    hmr: {
      protocol: "ws",
      host: "127.0.0.1",
      port: 5183,
    },
    watch: {
      ignored: ["**/src-tauri/**"],
    },
  },
  envPrefix: ["VITE_", "TAURI_"],
  build: {
    target: "es2021",
    minify: "esbuild",
    sourcemap: false,
  },
});
