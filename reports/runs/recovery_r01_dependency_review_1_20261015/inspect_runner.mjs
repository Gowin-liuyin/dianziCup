import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

const entry = pathToFileURL(resolve("node_modules/vitest/dist/node.js"));
const { resolveConfig } = await import(entry.href);
const { vitestConfig } = await resolveConfig({ config: "./vite.config.ts" });
const selected = Object.fromEntries([
  "environment", "globals", "pool", "isolate", "maxWorkers", "fileParallelism",
  "passWithNoTests", "include", "exclude", "coverage",
].map((name) => [name, vitestConfig[name]]));
if (selected.environment !== "jsdom" || selected.globals !== false || selected.pool !== "forks"
  || selected.isolate !== true || selected.maxWorkers !== 1 || selected.fileParallelism !== false
  || selected.passWithNoTests === true || selected.coverage.enabled === true) {
  throw new Error("The effective runner does not preserve the frozen fixture checks");
}
console.log(JSON.stringify(selected, null, 2));
