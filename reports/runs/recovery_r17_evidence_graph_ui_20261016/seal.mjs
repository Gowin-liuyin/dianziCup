import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const runDirectory = fileURLToPath(new URL(".", import.meta.url));
const workspace = fileURLToPath(new URL("../../..", import.meta.url));
const baseline = "8a1b04d48346d8550f0326a77f003246a0ebbab5";
const freeze = "b58aac48eee7e50264e3f51821c8057af36433d7";
const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");
const lfBytes = (bytes) => Buffer.from(bytes.toString("utf8").replace(/\r\n/g, "\n"));
const changed = execFileSync("git", ["diff", "--name-only", baseline, freeze], { cwd: workspace, encoding: "utf8" }).trim().split(/\r?\n/).filter((name) => name.startsWith("frontend/"));
const source = changed.map((name) => {
  const bytes = readFileSync(path.join(workspace, name));
  const gitBytes = execFileSync("git", ["show", `${freeze}:${name}`], { cwd: workspace });
  const gitBlob = execFileSync("git", ["rev-parse", `${freeze}:${name}`], { cwd: workspace, encoding: "utf8" }).trim();
  const matchesFrozenBlob = sha256(lfBytes(bytes)) === sha256(gitBytes);
  if (!matchesFrozenBlob) throw new Error(`Source differs from freeze: ${name}`);
  return { path: name, bytes: bytes.length, raw_sha256: sha256(bytes), lf_sha256: sha256(lfBytes(bytes)), git_blob: gitBlob, frozen_blob_sha256: sha256(gitBytes), matches_frozen_blob: matchesFrozenBlob };
});
function walk(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const target = path.join(directory, entry.name);
    return entry.isDirectory() ? walk(target) : [target];
  });
}
const evidenceFiles = [...walk(runDirectory).filter((name) => !["artifact_manifest.json", "seal.stdout.log", "seal.stderr.log"].includes(path.basename(name))), path.join(workspace, "reports/tasks/R17-evidence-graph-design.md"), path.join(workspace, "reports/tasks/R17-evidence-graph-ui.md")];
const evidence = evidenceFiles.map((name) => {
  const bytes = readFileSync(name); const isText = path.extname(name) !== ".png";
  return { path: path.relative(workspace, name).split(path.sep).join("/"), bytes: bytes.length, raw_sha256: sha256(bytes), ...(isText ? { lf_sha256: sha256(lfBytes(bytes)) } : {}) };
});
const credentialPattern = /\b(?:api[_-]?key|password|secret)\s*[:=]\s*["'][A-Za-z0-9_+/=-]{12,}["']/gi;
const credentialFindings = [];
for (const name of changed) {
  const content = readFileSync(path.join(workspace, name), "utf8");
  if (credentialPattern.test(content)) credentialFindings.push(name);
  credentialPattern.lastIndex = 0;
}
const fixtureMarkers = ["合成大图", "合成 Fixture · AI 组件安全事件", "isolated-graph-fixture-user", "合成证据：保存修订的定位片段。"];
const productionJavaScript = walk(path.join(workspace, "frontend/dist")).filter((name) => name.endsWith(".js")).map((name) => readFileSync(name, "utf8")).join("\n");
const markerFindings = fixtureMarkers.filter((marker) => productionJavaScript.includes(marker));
const tsbuildinfoMatches = readFileSync(path.join(workspace, "frontend/tsconfig.tsbuildinfo")).equals(execFileSync("git", ["show", `${freeze}:frontend/tsconfig.tsbuildinfo`], { cwd: workspace }));
if (credentialFindings.length || markerFindings.length || !tsbuildinfoMatches) throw new Error("Scoped seal checks failed");
writeFileSync(path.join(runDirectory, "artifact_manifest.json"), `${JSON.stringify({ schema_version: 1, recorded_at: new Date(Date.now() + 8 * 3600000).toISOString().replace("Z", "+08:00"), baseline, source_freeze: freeze, source, evidence, checks: { credential_shaped_literal_findings: credentialFindings, fixture_markers_in_current_production_js: markerFindings, tsbuildinfo_matches_frozen_head_blob: tsbuildinfoMatches }, scope_notes: "Only this slice and owned run files. Fixture content is synthetic; App registration and backend/live/manual are not_run. Hash is integrity metadata, not a secrecy or authenticity proof." }, null, 2)}\n`);
process.stdout.write(`${JSON.stringify({ source_count: source.length, evidence_count: evidence.length, credential_findings: credentialFindings.length, fixture_marker_findings: markerFindings.length, tsbuildinfoMatches })}\n`);
