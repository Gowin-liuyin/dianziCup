import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/**
 * 开发骨架阶段的构建配置。
 * 不配置任何真实 API 代理: 后端 API 由 T03+ 接入, 当前前端显式呈现未连接状态。
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: false,
  },
});
