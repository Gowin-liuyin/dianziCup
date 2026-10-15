import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const workspace = fileURLToPath(new URL("../../..", import.meta.url));
const run = fileURLToPath(new URL(".", import.meta.url));
const baseline = "370f8736f212adfc6ba05b0221bafa5061962a5c";
const files = execFileSync("git", ["diff", "--name-only", "8a1b04d48346d8550f0326a77f003246a0ebbab5", baseline], { cwd: workspace, encoding: "utf8" }).trim().split(/\r?\n/).filter((name) => name.startsWith("frontend/"));
const entries = files.map((name) => {
  const target = path.resolve(run, "original_snapshot/frozen_source", name);
  if (!target.startsWith(path.resolve(run, "original_snapshot/frozen_source") + path.sep)) throw new Error("Archive path escaped owned run");
  const bytes = execFileSync("git", ["show", `${baseline}:${name}`], { cwd: workspace });
  mkdirSync(path.dirname(target), { recursive: true }); writeFileSync(target, bytes);
  return { path: name, archive_path: path.relative(workspace, target).split(path.sep).join("/"), git_blob: execFileSync("git", ["rev-parse", `${baseline}:${name}`], { cwd: workspace, encoding: "utf8" }).trim(), lf_sha256: createHash("sha256").update(bytes).digest("hex"), bytes: bytes.length };
});
writeFileSync(path.join(run, "original_source_archive.json"), `${JSON.stringify({ baseline, tree: execFileSync("git", ["show", "--no-patch", "--format=%T", baseline], { cwd: workspace, encoding: "utf8" }).trim(), entries, note: "Original Git LF blobs; earlier raw worktree copies and independent reviewer raw copies remain unchanged in original_snapshot." }, null, 2)}\n`);
process.stdout.write(`${JSON.stringify({ baseline, original_source_files: entries.length })}\n`);
