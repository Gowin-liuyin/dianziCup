import process from "node:process";
import { randomUUID } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, realpathSync, writeFileSync } from "node:fs";
import { dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

const frontend = new URL(process.env.DIANZI_R17_FRONTEND_URL ?? "http://127.0.0.1:25173");
if (frontend.protocol !== "http:" || frontend.hostname !== "127.0.0.1" || !frontend.port || frontend.username || frontend.password || frontend.pathname !== "/" || frontend.search || frontend.hash) {
  throw new Error("R17 browser verification requires one dedicated loopback frontend origin");
}

const ownedRunRoot = fileURLToPath(new URL("../../reports/runs/r17_real_workbench_e2e_20261017/", import.meta.url));
const ownedExternalRoot = process.platform === "win32" ? "D:/dianzi-runtime-cache/r17-real-workbench-e2e-20261017" : "/tmp/dianzi-r17-real-workbench-e2e-20261017";

function isWithin(root: string, path: string): boolean {
  const location = relative(root, path);
  return !isAbsolute(location) && location !== ".." && !location.startsWith(`..${sep}`);
}

function resolveExistingParents(path: string): string {
  let existing = path;
  while (!existsSync(existing)) existing = dirname(existing);
  return resolve(realpathSync(existing), relative(existing, path));
}

/** Both lexical and existing-parent paths must remain in this task's owned output roots. */
export function resolveR17OutputRoot(value = join(ownedRunRoot, "browser-runs")): string {
  if (!isAbsolute(value) || value.includes("\0")) throw new Error("R17 output root must be an absolute owned path");
  const target = resolve(value);
  if (![ownedRunRoot, ownedExternalRoot].some((root) => isWithin(resolve(root), target) && relative(resolve(root), resolveExistingParents(resolve(root))) === "" && isWithin(resolveExistingParents(resolve(root)), resolveExistingParents(target)))) {
    throw new Error("R17 output root escapes the owned run or external cache directory");
  }
  return target;
}

const runId = process.env.DIANZI_R17_RUN_ID;
if (runId === undefined || !/^[a-z0-9][a-z0-9_-]{0,63}$/.test(runId)) throw new Error("R17 requires a unique lowercase run id before collecting or executing tests");
if (/^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])$/.test(runId)) throw new Error("R17 run id cannot use a reserved Windows device name");
const outputRoot = resolveR17OutputRoot(process.env.DIANZI_R17_OUTPUT_ROOT);
const runDirectory = join(outputRoot, runId);
const reservationPath = join(runDirectory, "reservation.json");
const inheritedNonce = process.env.DIANZI_R17_OWNER_NONCE;
if (inheritedNonce !== undefined) {
  const record: unknown = JSON.parse(readFileSync(reservationPath, "utf8"));
  if (typeof record !== "object" || record === null || !("run_id" in record) || !("owner_nonce" in record) || !("owner_pid" in record) || record.run_id !== runId || record.owner_nonce !== inheritedNonce || (record.owner_pid !== process.pid && record.owner_pid !== process.ppid)) {
    throw new Error("R17 inherited reservation does not belong to this test invocation");
  }
} else {
  mkdirSync(outputRoot, { recursive: true });
  mkdirSync(runDirectory);
  const ownerNonce = randomUUID();
  writeFileSync(reservationPath, JSON.stringify({ run_id: runId, owner_nonce: ownerNonce, owner_pid: process.pid, created_at: new Date().toISOString() }) + "\n", { flag: "wx" });
  process.env.DIANZI_R17_OWNER_NONCE = ownerNonce;
}

/** Root owns service lifecycle; this suite never starts or reuses a guessed backend. */
export default defineConfig({
  testDir: ".",
  testMatch: "r17-real-workbench.spec.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 25_000,
  expect: { timeout: 8_000 },
  outputDir: join(runDirectory, "artifacts"),
  reporter: [["list"], ["json", { outputFile: join(runDirectory, "results.json") }]],
  use: {
    baseURL: frontend.origin,
    channel: "msedge",
    viewport: { width: 1366, height: 900 },
    trace: "off",
    video: "off",
    screenshot: "off",
  },
});
