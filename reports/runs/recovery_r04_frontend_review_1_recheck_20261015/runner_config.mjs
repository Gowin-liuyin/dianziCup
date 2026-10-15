import { writeFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const run = path.dirname(fileURLToPath(import.meta.url));
const frontend = 'C:/Users/yinha/.codex/worktrees/recovery-r04-frontend-recheck/dianzi/frontend';
const { createVitest } = await import(pathToFileURL(path.join(frontend, 'node_modules/vitest/dist/node.js')).href);
const ctx = await createVitest('test', { root: frontend, run: true });
try {
  const receipt = { candidate: '7f9b6f14e3c7c5ff451fab183f959a11d8daf114', command: 'node runner_config.mjs; createVitest(test,{root:fixedFrontend,run:true})', checked_at: new Date().toISOString(), global: { pool: ctx.config.pool, isolate: ctx.config.isolate, maxWorkers: ctx.config.maxWorkers, fileParallelism: ctx.config.fileParallelism, environment: ctx.config.environment, exclude: ctx.config.exclude }, projects: ctx.projects.map((project) => ({ pool: project.config.pool, isolate: project.config.isolate, maxWorkers: project.config.maxWorkers, fileParallelism: project.config.fileParallelism, environment: project.config.environment })) };
  await writeFile(path.join(run, 'runner-config.json'), JSON.stringify(receipt, null, 2));
  console.log(JSON.stringify(receipt));
} finally {
  await ctx.close();
}

