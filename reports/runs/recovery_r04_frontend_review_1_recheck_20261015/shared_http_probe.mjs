import { createRequire } from 'node:module';
import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const run = path.dirname(fileURLToPath(import.meta.url));
const frontend = 'C:/Users/yinha/.codex/worktrees/recovery-r04-frontend-recheck/dianzi/frontend';
const require = createRequire(`${frontend}/package.json`);
const ts = require('typescript');
const now = () => new Date().toLocaleString('sv-SE', { timeZone: 'Asia/Shanghai' }).replace(' ', 'T') + '+08:00';
const startedAt = now();
const source = await readFile(path.join(frontend, 'src/api/client.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText;
globalThis.window = globalThis;
const { fetchJson } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
const cases = [];
const marker = 'independent upstream private HTML must stay absent';
for (const status of [401, 403, 503]) {
  for (const mode of ['empty', 'html']) {
    let options;
    globalThis.fetch = async (_path, requestOptions) => { options = requestOptions; return new Response(mode === 'empty' ? '' : `<html>${marker}</html>`, { status, headers: { 'Content-Type': 'text/html' } }); };
    let error;
    try { await fetchJson('/v1/events?limit=20'); } catch (failure) { error = failure; }
    const expectedCode = status === 401 ? 'unauthenticated' : status === 403 ? 'forbidden' : 'service_unavailable';
    const passed = error?.status === status && error?.code === expectedCode && !error?.message?.includes(marker) && error?.retryable === (status >= 500) && options?.credentials === 'include' && options?.cache === 'no-store';
    cases.push({ id: `${mode}-http-${status}`, passed, status: error?.status, code: error?.code, public_message: error?.message, retryable: error?.retryable, upstream_text_exposed: error?.message?.includes(marker) ?? false });
  }
}
globalThis.fetch = async () => new Response(`<html>${marker}</html>`, { status: 200 });
let malformedError;
try { await fetchJson('/v1/events?limit=20'); } catch (failure) { malformedError = failure; }
cases.push({ id: 'successful-non-json-remains-contract-failure', passed: malformedError?.status === 502 && malformedError?.code === 'invalid_response' && !malformedError?.message?.includes(marker), status: malformedError?.status, code: malformedError?.code });
globalThis.fetch = async () => new Response(JSON.stringify({ schema_version: 2, items: [], next_cursor: null, data_mode: 'fixture' }), { status: 200, headers: { 'Content-Type': 'application/json' } });
const success = await fetchJson('/v1/events?limit=20');
cases.push({ id: 'successful-valid-json-not-rewritten', passed: success.schema_version === 2 && success.items.length === 0 && success.data_mode === 'fixture' });
const receipt = { started_at: startedAt, ended_at: now(), candidate: '7f9b6f14e3c7c5ff451fab183f959a11d8daf114', command: 'node shared_http_probe.mjs', execution: 'compile exact fixed client.ts in memory; no business writes and no external requests', cases, summary: { passed: cases.filter((item) => item.passed).length, failed: cases.filter((item) => !item.passed).length, skipped: 0 } };
await writeFile(path.join(run, 'shared-http-probe.json'), JSON.stringify(receipt, null, 2));
console.log(JSON.stringify(receipt));
process.exitCode = receipt.summary.failed ? 1 : 0;
