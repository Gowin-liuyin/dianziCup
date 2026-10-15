import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";

const runPath = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(runPath, "../../..");
const prefix = "reports/runs/recovery_r17_assets_workbench_20261016";
const base = "e310f7735bd499c4d9fbcefe8a644e2309a16a62";
const graphMaterial = "164cae93ac888180b056a4c694011402ee387383";
const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");
const now = () => new Date(Date.now() + 8 * 60 * 60 * 1000).toISOString().replace("Z", "+08:00");
const git = (...args) => execFileSync("git", args, { cwd: root });
const json = (name, value) => writeFileSync(path.join(runPath, name), JSON.stringify(value, null, 2) + "\n");
function filesIn(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => entry.isDirectory() ? filesIn(path.join(directory, entry.name)) : [path.join(directory, entry.name)]);
}
function edgeReport(name) {
  const raw = readFileSync(path.join(runPath, name), "utf8");
  const start = raw.indexOf("{");
  if (start < 0) throw new Error("Edge JSON report was not found in raw stdout");
  return JSON.parse(raw.slice(start));
}

const businessPaths = ["frontend/src/App.tsx", "frontend/src/app/workspace-navigation.ts", ...filesIn(path.join(root, "frontend/src/features/assets")).map((file) => path.relative(root, file).replaceAll("\\", "/")), "frontend/e2e/r17-assets.fixture.ts", "frontend/e2e/r17_assets_fixture.spec.ts", "frontend/tests/t42_assets_assessment_ui.test.tsx"];
const currentCode = git("rev-parse", "HEAD").toString().trim();
const sourcePaths = ["backend/src/ai_intel/assets/inventory_contracts.py", "backend/src/ai_intel/assets/inventory_routes.py", "backend/src/ai_intel/assets/inventory.py", "backend/src/ai_intel/assets/manifest_parser.py", "backend/src/ai_intel/domain/access.py", "frontend/src/api/client.ts", "frontend/src/app/auth-session.tsx", "frontend/src/styles.css", "docs/plan/00_execution_map.md", "docs/plan/03_data_contracts.md", "docs/plan/04_workflows_and_algorithms.md", "docs/plan/05_api_and_tool_contracts.md", "docs/plan/12_recovery_task_cards_20261014.md", "docs/tasks/T42_assets_assessment_ui.md", "docs/decisions/CR-R11_asset_inventory.md", "frontend/package-lock.json", "backend/uv.lock", "frontend/tsconfig.tsbuildinfo"];

if (process.argv.includes("--source")) {
  const diff = git("diff", "--binary", "9be85d7", currentCode, "--", ...businessPaths);
  writeFileSync(path.join(runPath, "business.diff.gz"), gzipSync(diff));
  json("source_receipt.json", {
    recorded_at: now(), base, reviewed_graph_material: graphMaterial, graph_source: git("rev-parse", "baa9").toString().trim(), prerequisite_merge: "9be85d7",
    code_first: git("rev-parse", "3f1553b7").toString().trim(), code_final: currentCode,
    final_difference_from_tested_tree: "1acf4911 only removes one fixture EOF blank line; runtime logic and tests are unchanged",
    business_paths: businessPaths, source_diff_uncompressed_sha256: sha256(diff), source_diff_uncompressed_bytes: diff.length,
    frozen_local_sources: sourcePaths.map((file) => ({ path: file, working_sha256: sha256(readFileSync(path.join(root, file))), base_git_blob: git("rev-parse", `${base}:${file}`).toString().trim(), unchanged_from_base: git("diff", "--name-only", base, "HEAD", "--", file).length === 0 })),
    external_reference: [{ path: "E:/wechatData/xwechat_files/wxid_c14weta2ez6m22_03f5/msg/file/2026-10/ui-design.md", sha256: sha256(readFileSync("E:/wechatData/xwechat_files/wxid_c14weta2ez6m22_03f5/msg/file/2026-10/ui-design.md")), authority: "design reference only; no adjacent files read" }],
    runtime: { node: process.version, npm: "11.8.0", browser: "Microsoft Edge via Playwright channel msedge", dependencies: "existing D:/dianzi/frontend/node_modules junction; no install or lock change" },
  });
  const edge = edgeReport("edge_delivery.log");
  json("edge_delivery_report.json", edge);
  json("verification_summary.json", {
    recorded_at: now(), fixture_only: true, live: "not_run / root controlled real backend integration pending", manual: "not_run; author inspected synthetic screenshots only",
    contract: { passed: 6, failed: 0, skipped: 0 }, client: { passed: 6, failed: 0, skipped: 0 }, component: { passed: 10, failed: 0, skipped: 0 },
    frontend_regression: { passed: 447, failed: 0, skipped: 0, existing: 425, added: 22, log: "regression_delivery.log" },
    edge_fixture: { asset_scenarios: 6, existing_graph_scenarios: 6, ...edge.stats, log: "edge_delivery.log" },
    source_style: { first_exit: 2, final_exit: 0, first_reason: "extra blank line at fixture EOF; local source commit proceeded before the shell exit was gated; separate 1acf4911 fixes it" },
    built_bundle_contains_synthetic_fixture_payload: filesIn(path.join(root, "frontend/dist/assets")).filter((file) => file.endsWith(".js")).some((file) => /Synthetic fixture|synthetic-demo-package/.test(readFileSync(file, "utf8"))),
  });
  process.stdout.write(JSON.stringify({ code: currentCode, edge: edge.stats.expected, regression: 447 }) + "\n");
} else if (process.argv.includes("--verify")) {
  const manifest = JSON.parse(readFileSync(path.join(runPath, "raw_manifest.json"), "utf8"));
  const differences = manifest.files.filter((entry) => sha256(readFileSync(path.join(root, entry.path))) !== entry.sha256 || sha256(git("show", `:0:${entry.path}`)) !== entry.sha256);
  process.stdout.write(JSON.stringify({ checked_at: now(), files: manifest.files.length, working_or_staged_byte_differences: differences.length }) + "\n");
  if (differences.length) process.exitCode = 1;
} else {
  const reportFiles = filesIn(runPath).filter((file) => !["raw_manifest.json", "raw_manifest.sha256"].includes(path.basename(file)));
  const byteAudit = [...businessPaths, ".gitattributes", ...reportFiles.map((file) => path.relative(root, file).replaceAll("\\", "/"))].filter((file) => file !== `${prefix}/git_byte_audit.json`).map((file) => {
    const bytes = readFileSync(path.join(root, file));
    let blob = null;
    try { blob = git("show", `:0:${file}`); } catch { blob = null; }
    return { path: file, raw_sha256: sha256(bytes), raw_bytes: bytes.length, staged_sha256: blob === null ? null : sha256(blob), staged_bytes: blob?.length ?? null, byte_equal: blob === null ? null : bytes.equals(blob) };
  });
  json("git_byte_audit.json", { recorded_at: now(), core_autocrlf: "true", report_raw_attribute: `${prefix}/** -text`, files: byteAudit, staged_report_differences: byteAudit.filter((entry) => entry.path.startsWith(prefix + "/") && entry.byte_equal === false).length });
  const rawFiles = filesIn(runPath).filter((file) => !["raw_manifest.json", "raw_manifest.sha256"].includes(path.basename(file)));
  const manifest = { recorded_at: now(), source_commit: currentCode, scope: "synthetic author evidence only; no raw private asset input", files: rawFiles.map((file) => { const bytes = readFileSync(file); return { path: path.relative(root, file).replaceAll("\\", "/"), bytes: bytes.length, sha256: sha256(bytes) }; }) };
  json("raw_manifest.json", manifest);
  writeFileSync(path.join(runPath, "raw_manifest.sha256"), sha256(readFileSync(path.join(runPath, "raw_manifest.json"))) + "  raw_manifest.json\n");
  process.stdout.write(JSON.stringify({ files: rawFiles.length, report_byte_differences: byteAudit.filter((entry) => entry.path.startsWith(prefix + "/") && entry.byte_equal === false).length, source: currentCode }) + "\n");
}
