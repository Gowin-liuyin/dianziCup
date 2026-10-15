import { spawnSync } from "node:child_process";
import { appendFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const runDirectory = fileURLToPath(new URL(".", import.meta.url));
const [label, command, ...args] = process.argv.slice(2);
if (!label || !command || !/^[a-z0-9-]+$/.test(label)) throw new Error("label and argv required");
function shanghaiTime() { return new Date(Date.now() + 8 * 3600000).toISOString().replace("Z", "+08:00"); }
const start = shanghaiTime();
const result = spawnSync(command, args, { cwd: process.cwd(), encoding: "utf8", timeout: 180000, windowsHide: true });
writeFileSync(`${runDirectory}/${label}.stdout.log`, result.stdout ?? "");
writeFileSync(`${runDirectory}/${label}.stderr.log`, result.stderr ?? "");
appendFileSync(`${runDirectory}/commands.jsonl`, `${JSON.stringify({ label, cwd: process.cwd(), argv: [command, ...args], start, end: shanghaiTime(), exit_code: result.status, signal: result.signal, runner_error: result.error?.message ?? null })}\n`);
process.stdout.write((result.stdout ?? "").slice(-4500));
process.stderr.write((result.stderr ?? "").slice(-2500));
process.exit(result.status ?? 1);
