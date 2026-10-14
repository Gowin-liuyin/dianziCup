import react from "@vitejs/plugin-react";
import process from "node:process";
import { configDefaults, defineConfig } from "vitest/config";

/** 本地同源代理保留浏览器 Origin 与 Cookie；端口冲突直接失败，不复用其他开发服务。 */
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 25173,
    strictPort: true,
    proxy: { "/v1": { target: process.env.API_PROXY_TARGET ?? "http://127.0.0.1:28002", changeOrigin: false } },
  },
  test: {
    environment: "jsdom",
    globals: false,
    maxWorkers: 1,
    fileParallelism: false,
    exclude: [...configDefaults.exclude, "e2e/**"],
  },
});
