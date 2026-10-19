# R17 JUnit metadata-only provenance review

What this change does: This review traces one withheld XML match to its frozen test fixture. It records hashes and AST locations only. No source, original report, task state, scanner setting, threshold or exemption was changed.

Task status: `awaiting_review` for this provenance record. Whole R17 remains `in_progress / partial`; this record does not accept R17 or a stage.

Frozen source: `D:/wt/r17-root-investigation-sdk-review1`, commit `a576fc1f88cd82bc13e5bed9a4c7a013bb8cd74b`. The working tree was clean when inspected. Read instructions: AGENTS.md, the execution map, the R17 recovery card, R17 state and recent handoff, and Ponytail review skill version 5.3.0.

## Exact identity and location

| Evidence | Metadata |
|---|---|
| Original XML | `D:/dianzi/reports/runs/recovery_reviewed_integration_20261016/frontend_batch10_unit.xml` |
| Original bytes / SHA-256 | `217296` / `3364188a1248f3d4d04f687bf762a94987660e0683acafafd93ebe92129b8032` |
| Frozen withheld record SHA-256 | `ef5d578b8711609f9a12dbf0aa1f8caf0ecdd830cdb8f55380ccb53fed1cc2fa` |
| Exact matched byte span | `[119717, 119750)`; end is exclusive; 33 bytes |
| Match SHA-256 | `40c0ba9eb567c500774ff84544f44c2d98414527c20306f4cd1666437cbdd49d` |
| XML location | `testcase` opening `name` attribute, rather than testcase body |
| Containing testcase span | `[119555, 119803)` |
| Testcase name SHA-256 | `22e7f2de123a3d66f0e237b6538786d159b77615f3224701e6b45861bfa7c6e8` |
| Testcase class path | `src/features/assets/sbom-contracts.test.ts` |
| Testcase class name SHA-256 | `509e90c3dce54e383d1b309ef4b7e48b144eebb0f6604492332c6e2e491d06d1` |

The containing testcase has no `failure`, `error` or `skipped` element. This is a reading of the original XML, not a fresh test result.

## Fixture and flow

TypeScript compiler 5.7.3 parsed 151 TypeScript files in the frozen frontend `src`, `tests` and `e2e` directories. Exactly one string-literal value contained the matched bytes.

- Source: `frontend/src/features/assets/sbom-contracts.test.ts`, line 46, column 41; source SHA-256 `5c2e79b57c80c07030f735442ed51736474c031e3097abdc2e500c518dba1bef`.
- AST node: `StringLiteral` inside `ArrayLiteralExpression`, row index 1 of `it.each` input. Literal source span is `[4684, 4733)`; the same matched bytes are at source `[4685, 4718)`.
- Full literal value: 47 characters, SHA-256 `614bbb1db6432960e008489852fbc71f2e43184584d05754d8bd2185f0c2ff3b`. The original match is a substring, not the whole literal.
- The parameterized title with this row inserted is a suffix of the exact original testcase name. Expanded title SHA-256: `83fe61e0f121792575049c86fcaa9ffb6adc63d66b8d78c5fb51530ad799ee06`.
- Callback line 47 passes parameter `uri` directly to `isSafeSbomDocumentUri`, then uses `expect(...).toBe(false)`.
- The validator is in `frontend/src/features/assets/sbom-contracts.ts`, line 47, source SHA-256 `378e2c6b5e68880e5b4e8374dc1770900bd0a32dbe3bd076007e8e500aa2c593`. Its local helper `decoded` starts at line 36.
- The validator and helper AST contain URL parsing, regular expressions, strings, numbers and `decodeURIComponent`. The inspected call chain has no network or credential client call.
- An in-memory URL shape check of the complete literal finds username and password fields and a reserved example/test host. It is a static test table literal, not an environment or secret-store read. No literal, credential value, host text, original test name or surrounding source/XML text was emitted.

Classification: `test_only_synthetic_invalid_uri_literal_echoed_in_parameterized_test_name` for this exact XML SHA-256 and byte span. The inspected flow is an unsafe-URI rejection fixture; it does not pass the values to authentication, a database connection or a network client.

## Actual verification and limits

The metadata probe command was run five times while narrowing the read-only AST trace:

`node 'D:/dianzi/reports/runs/r17_root_junit_provenance_review1_20261017/junit_provenance.cjs'`

All five executions exited 0. The first inspected only `frontend/tests` and found no literal; the later probes included the actual `src` testcase and its parser. The final metadata and final script are sealed by `seal_manifest.json`. Probe execution receipts are in `probe_execution_receipt.json`.

New tests run: 0. Unit, integration, live and manual verification for new execution are `not_run`. No PostgreSQL, browser, paid API or scanner was used. No secret store or key was read. There is no plan/contract deviation or scoring acceptance from this auxiliary trace.

Not proved: the original batch command was not rerun; actual-secret exact comparison was not performed; this is not a statement that the full XML or repository has no secrets. Static fixture provenance and the original testcase result cannot replace those checks.

Verdict: Ship this exact metadata classification for root review. It creates no scanner exemption. Any next scanner decision must retain the exact original hash/span and the normal priority of actual-secret matching.

Only files in `reports/runs/r17_root_junit_provenance_review1_20261017` were added or edited by this agent. The next step is root review of this sealed metadata before any narrow classification registration.
