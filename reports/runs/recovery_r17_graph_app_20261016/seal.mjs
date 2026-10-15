import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const runDirectory = fileURLToPath(new URL(".", import.meta.url));
const root = fileURLToPath(new URL("../../../", import.meta.url));
const codeGit = "baa9fa7e024981f8a5516bd840e49910ce7cd1f9";
function digest(bytes) { return createHash("sha256").update(bytes).digest("hex"); }
function git(...args) {
  const result = spawnSync("git", args, { cwd: root, windowsHide: true });
  if (result.status !== 0) throw new Error(`git ${args[0]} failed`);
  return result.stdout;
}
function entry(path) {
  const raw = readFileSync(path);
  const label = relative(root, path).replaceAll("\\", "/");
  const binary = path.endsWith(".png");
  return { path: label, bytes: raw.length, raw_sha256: digest(raw), lf_text_sha256: binary ? null : digest(Buffer.from(raw.toString("utf8").replaceAll("\r\n", "\n"))) };
}
function walk(directory) {
  return readdirSync(directory).sort().flatMap((name) => {
    const path = join(directory, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
}
const sourcePaths = git("diff", "--name-only", `${codeGit}^`, codeGit).toString("utf8").trim().split("\n");
const sourceGit = sourcePaths.map((path) => {
  const blob = git("show", `${codeGit}:${path}`);
  const working = entry(join(root, path));
  if (digest(blob) !== working.lf_text_sha256) throw new Error(`source drift: ${path}`);
  return { ...working, code_git: codeGit, git_blob: git("rev-parse", `${codeGit}:${path}`).toString("utf8").trim(), git_lf_sha256: digest(blob) };
});
const materials = walk(runDirectory).filter((path) => !["artifact_manifest.json", "artifact_manifest.sha256"].some((name) => path.endsWith(`/${name}`) || path.endsWith(`\\${name}`))).map(entry);
materials.push(entry(join(root, "reports/tasks/R17-graph-app.md")));
materials.push(entry(join(root, ".gitattributes")));
const bundles = walk(join(root, "frontend/dist")).map(entry);
const manifest = {
  schema_version: 1, sealed_at: new Date(Date.now() + 8 * 3600000).toISOString().replace("Z", "+08:00"),
  task: "R17-graph-app", status: "awaiting_review", code_git: codeGit,
  code_tree: git("rev-parse", `${codeGit}^{tree}`).toString("utf8").trim(),
  base_git: "136fbaef337036d95229aa4976c1ba49b2e6b04c", merged_graph_git: "65497b14cb5c24c6d780f675a70af3ee4019d8db", backend_read_only_git: "08b141bd437c1de70a8435a1f7f6c448a131ed0d",
  sourceGit, materials, bundles,
  limits: { browser: "isolated frontend HTTP fixtures, actual local Edge", pg_api_integration: "not_run", live: "not_run", independent_manual: "not_run", original_red_preserved: true },
};
const bytes = Buffer.from(`${JSON.stringify(manifest, null, 2)}\n`);
writeFileSync(join(runDirectory, "artifact_manifest.json"), bytes);
writeFileSync(join(runDirectory, "artifact_manifest.sha256"), `${digest(bytes)}  artifact_manifest.json\n`);
process.stdout.write(`${JSON.stringify({ code_git: codeGit, source_files: sourceGit.length, raw_materials: materials.length, manifest_sha256: digest(bytes) })}\n`);
