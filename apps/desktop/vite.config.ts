import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Tauri 推荐的 Vite 配置：
// - 固定端口 5173（与 tauri.conf.json 的 devUrl 一致）
// - 关闭 HMR overlay 强制清屏以避免 macOS 焦点问题
// - 显式 clearScreen=false 让 Tauri 自己控制
export default defineConfig(async () => ({
  plugins: [react()],
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
}));
