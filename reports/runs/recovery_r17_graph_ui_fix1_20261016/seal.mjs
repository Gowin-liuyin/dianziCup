import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const run = fileURLToPath(new URL(".", import.meta.url));
const workspace = fileURLToPath(new URL("../../..", import.meta.url));
const baseline = "370f8736f212adfc6ba05b0221bafa5061962a5c";
const freeze = "d6537678efe98c38e08b70960a7e5edaac02b108";
const hash = (bytes) => createHash("sha256").update(bytes).digest("hex");
const lf = (bytes) => Buffer.from(bytes.toString("utf8").replace(/\r\n/g, "\n"));
const sourceNames = execFileSync("git", ["diff", "--name-only", baseline, freeze], { cwd: workspace, encoding: "utf8" }).trim().split(/\r?\n/);
const source = sourceNames.map((name) => {
  const bytes = readFileSync(path.join(workspace, name)); const gitBytes = execFileSync("git", ["show", `${freeze}:${name}`], { cwd: workspace });
  const matches = hash(lf(bytes)) === hash(gitBytes); if (!matches) throw new Error(`Source differs from freeze: ${name}`);
  return { path: name, raw_sha256: hash(bytes), lf_sha256: hash(lf(bytes)), bytes: bytes.length, git_blob: execFileSync("git", ["rev-parse", `${freeze}:${name}`], { cwd: workspace, encoding: "utf8" }).trim(), frozen_blob_sha256: hash(gitBytes), matches_frozen_blob: matches };
});
function walk(directory) { return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => { const target = path.join(directory, entry.name); return entry.isDirectory() ? walk(target) : [target]; }); }
const excluded = new Set(["artifact_manifest.json", "artifact_manifest.sha256", "seal.stdout.log", "seal.stderr.log"]);
const evidenceFiles = [...walk(run).filter((name) => !excluded.has(path.basename(name))), path.join(workspace, "reports/tasks/R17-graph-ui-fix1.md")];
const evidence = evidenceFiles.map((name) => { const bytes = readFileSync(name); return { path: path.relative(workspace, name).split(path.sep).join("/"), raw_sha256: hash(bytes), bytes: bytes.length, ...(path.extname(name) === ".png" ? {} : { lf_sha256: hash(lf(bytes)) }) }; });
const reviewerManifestHash = hash(readFileSync(path.join(run, "original_snapshot/reviewer-artifact-manifest.json")));
if (reviewerManifestHash !== "812970796a9d0325ce1011876525b3aa5bfccbdda7454ff7101f430c9b21874e") throw new Error("Original reviewer manifest raw differs");
const tsbuildinfoMatches = readFileSync(path.join(workspace, "frontend/tsconfig.tsbuildinfo")).equals(execFileSync("git", ["show", `${freeze}:frontend/tsconfig.tsbuildinfo`], { cwd: workspace }));
const credentialPattern = /\b(?:api[_-]?key|password|secret)\s*[:=]\s*["'][A-Za-z0-9_+/=-]{12,}["']/gi;
const credentialFindings = [];
for (const name of sourceNames) { if (credentialPattern.test(readFileSync(path.join(workspace, name), "utf8"))) credentialFindings.push(name); credentialPattern.lastIndex = 0; }
const production = walk(path.join(workspace, "frontend/dist")).filter((name) => name.endsWith(".js")).map((name) => readFileSync(name, "utf8")).join("\n");
const fixtureMarkers = ["最大合成指针图", "合成多边端点", "graph-pointer-fixture-user"].filter((marker) => production.includes(marker));
if (!tsbuildinfoMatches || credentialFindings.length || fixtureMarkers.length) throw new Error("Scoped seal checks failed");
const bytes = Buffer.from(`${JSON.stringify({ schema_version: 1, recorded_at: new Date(Date.now() + 8 * 3600000).toISOString().replace("Z", "+08:00"), baseline, baseline_tree: "ec464bf91b7c2806cb7b2fbbcd0a2529dffbd985", source_freeze: freeze, source_tree: "08249b02142cd085d4c4c801469edcea6d2b1649", source, evidence, checks: { original_reviewer_manifest_raw_sha256: reviewerManifestHash, tsbuildinfo_matches_frozen_blob: tsbuildinfoMatches, credential_shaped_literal_findings: credentialFindings, fixture_markers_in_current_production_js: fixtureMarkers }, scope_notes: "Only fix1 source and owned artifacts. Original reviewer/author files read-only. All HTTP/browser data synthetic. Real API integration/live/manual remain not_run; manifest does not sign Must closure or entire R17." }, null, 2)}\n`);
writeFileSync(path.join(run, "artifact_manifest.json"), bytes); const digest = hash(bytes);
writeFileSync(path.join(run, "artifact_manifest.sha256"), `${digest}  artifact_manifest.json\n`);
process.stdout.write(`${JSON.stringify({ source_count: source.length, evidence_count: evidence.length, manifest_sha256: digest, reviewerManifestHash, tsbuildinfoMatches, credential_findings: credentialFindings.length, fixture_markers: fixtureMarkers.length })}\n`);
