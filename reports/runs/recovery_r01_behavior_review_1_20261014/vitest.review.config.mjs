import { defineConfig } from 'C:/Users/yinha/.codex/worktrees/recovery-r01-candidate/dianzi/frontend/node_modules/vitest/dist/config.js';
import react from 'C:/Users/yinha/.codex/worktrees/recovery-r01-candidate/dianzi/frontend/node_modules/@vitejs/plugin-react/dist/index.js';

export default defineConfig({
  root: 'D:/dianzi/reports/runs/recovery_r01_behavior_review_1_20261014',
  plugins: [react()],
  resolve: {
    alias: {
      react: 'C:/Users/yinha/.codex/worktrees/recovery-r01-candidate/dianzi/frontend/node_modules/react',
      'react-dom': 'C:/Users/yinha/.codex/worktrees/recovery-r01-candidate/dianzi/frontend/node_modules/react-dom',
      vitest: 'C:/Users/yinha/.codex/worktrees/recovery-r01-candidate/dianzi/frontend/node_modules/vitest/dist/index.js',
      '@testing-library/react': 'C:/Users/yinha/.codex/worktrees/recovery-r01-candidate/dianzi/frontend/node_modules/@testing-library/react/dist/index.js',
    },
  },
  test: {
    environment: 'jsdom',
    environmentOptions: { jsdom: {} },
    include: ['frontend_behavior.test.tsx'],
    maxWorkers: 1,
    fileParallelism: false,
  },
});
