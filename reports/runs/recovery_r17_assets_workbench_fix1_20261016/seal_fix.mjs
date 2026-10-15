import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';
const run = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(run, '../../..');
const sha = (bytes) => createHash('sha256').update(bytes).digest('hex');
const git = (...args) => execFileSync('git', args, { cwd: root });
const json = (name, value) => writeFileSync(path.join(run, name), JSON.stringify(value, null, 2) + '\n');
const now = () => new Date(Date.now() + 8 * 3600000).toISOString().replace('Z', '+08:00');
const paths = (directory) => readdirSync(directory, { withFileTypes: true }).flatMap((entry) => entry.isDirectory() ? paths(path.join(directory, entry.name)) : [path.join(directory, entry.name)]);
const relative = (file) => path.relative(root, file).replaceAll('\\', '/');
const base = '6db161e59e1c081d249b510ac441c93ad2fd295b';
const code = 'a25fd81c50f0ea14f44e7fda2c3edac5cab74d48';
const codePaths = ['frontend/src/features/assets/asset-contracts.ts', 'frontend/src/features/assets/asset-client.ts', 'frontend/src/features/assets/asset-workspace.tsx', 'frontend/src/features/assets/asset-status.tsx', 'frontend/src/features/assets/asset-scope.test.tsx'];
function reportFrom(name) { const raw = readFileSync(path.join(run, name), 'utf8'); return JSON.parse(raw.slice(raw.indexOf('{'))); }
if (process.argv.includes('--source')) {
  if (sha(readFileSync(path.join(run, 'independent.spec.cjs'))) !== '349b585720d400021385ada25c714ab262b52962e677e2547e83de13ca23205b') throw new Error('original independent probe changed');
  if (sha(readFileSync(path.join(run, 'reviewer_frozen.md'))) !== 'f5f7a0282deab873b959ce669a1960112e5f77a741db3e8b85bea9715f66342a') throw new Error('sealed reviewer report changed');
  const oldManifest = JSON.parse(readFileSync(path.join(root, 'reports/runs/recovery_r17_assets_workbench_20261016/raw_manifest.json'), 'utf8'));
  const oldDifferences = oldManifest.files.filter((entry) => sha(readFileSync(path.join(root, entry.path))) !== entry.sha256 || sha(git('show', `${base}:${entry.path}`)) !== entry.sha256);
  if (oldDifferences.length) throw new Error('original author material drift');
  const oldFixtures = ['frontend/src/features/assets/synthetic-fixtures.ts', 'frontend/src/features/assets/asset-contracts.test.ts', 'frontend/src/features/assets/asset-client.test.ts', 'frontend/tests/t42_assets_assessment_ui.test.tsx', 'frontend/e2e/r17-assets.fixture.ts', 'frontend/e2e/r17_assets_fixture.spec.ts', 'frontend/e2e/r17_graph_app_fixture.spec.ts'];
  const oldFixtureDiff = git('diff', '--name-only', base, '--', ...oldFixtures).toString();
  if (oldFixtureDiff) throw new Error('original fixture or expectation changed');
  const untouched = ['backend', 'frontend/src/api', 'frontend/src/app/auth-session.tsx', 'frontend/src/styles.css', 'frontend/package-lock.json', 'progress', 'contracts', 'fixtures', 'benchmarks'];
  const forbiddenDiff = git('diff', '--name-only', base, '--', ...untouched).toString();
  if (forbiddenDiff) throw new Error('forbidden source changed');
  const diff = git('diff', '--binary', base, code, '--', ...codePaths); writeFileSync(path.join(run, 'business.diff.gz'), gzipSync(diff));
  const results = Object.fromEntries(['independent_red', 'independent_green', 'edge_baseline', 'edge_late'].map((name) => { const parsed = reportFrom(name + '.log'); json(name + '_report.json', parsed); return [name, parsed.stats]; }));
  json('source_receipt.json', { recorded_at: now(), code, parent_material: base, scope: 'M01 private asset UI only; synthetic, no backend/live', code_paths: codePaths, original_author_raw_files: oldManifest.files.length, original_author_differences: oldDifferences.length, original_fixture_differences: [], forbidden_source_differences: [], original_probe_sha256: sha(readFileSync(path.join(run, 'independent.spec.cjs'))), frozen_reviewer_report_sha256: sha(readFileSync(path.join(run, 'reviewer_frozen.md'))), diff_uncompressed_sha256: sha(diff), diff_uncompressed_bytes: diff.length, results });
  process.stdout.write(JSON.stringify({ code, original_files: oldManifest.files.length, original_differences: 0, reports: results }) + '\n');
} else if (process.argv.includes('--verify')) {
  const manifest = JSON.parse(readFileSync(path.join(run, 'raw_manifest.json'), 'utf8'));
  const changed = manifest.files.filter((entry) => sha(readFileSync(path.join(root, entry.path))) !== entry.sha256 || sha(git('show', `:0:${entry.path}`)) !== entry.sha256);
  process.stdout.write(JSON.stringify({ checked_at: now(), files: manifest.files.length, staged_or_working_differences: changed.length }) + '\n');
  if (changed.length) process.exitCode = 1;
} else {
  const before = paths(run).filter((file) => !['raw_manifest.json', 'raw_manifest.sha256', 'git_byte_audit.json'].includes(path.basename(file)));
  const bytes = before.map((file) => { const raw = readFileSync(file); const staged = git('show', `:0:${relative(file)}`); return { path: relative(file), raw_bytes: raw.length, staged_bytes: staged.length, raw_sha256: sha(raw), staged_sha256: sha(staged), equal: raw.equals(staged) }; });
  json('git_byte_audit.json', { checked_at: now(), files: bytes, differences: bytes.filter((entry) => !entry.equal).length });
  if (bytes.some((entry) => !entry.equal)) throw new Error('raw Git bytes differ');
  const entries = paths(run).filter((file) => !['raw_manifest.json', 'raw_manifest.sha256'].includes(path.basename(file))).map((file) => { const raw = readFileSync(file); return { path: relative(file), bytes: raw.length, sha256: sha(raw) }; });
  json('raw_manifest.json', { recorded_at: now(), code, author: '/root/r17_asset_inventory_workbench_implementation', scope: 'M01 fix1 author evidence, all synthetic; awaiting independent recheck', files: entries });
  writeFileSync(path.join(run, 'raw_manifest.sha256'), sha(readFileSync(path.join(run, 'raw_manifest.json'))) + '  raw_manifest.json\n');
  process.stdout.write(JSON.stringify({ files: entries.length, raw_byte_differences: 0 }) + '\n');
}
