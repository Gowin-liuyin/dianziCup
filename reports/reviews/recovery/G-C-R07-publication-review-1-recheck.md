What this change does: The frozen combination checks source, document and revision permissions before object IO and before receipt replay. It shares the real source writer's lock order, keeps CVSS scoring authorities separate, and stores readable rule/event context in workflow schema2. The three Must findings from the first review are closed for this service slice.

Verdict: **Ship, limited to the R07 publication service slice at dc04d193.** This is not acceptance of whole R07, any original T card, or G-C. The reviewer did not implement these fixes and did not change business code, original tests, original probes, progress, accepted flags, Git commits or remote state.

## Frozen scope

- Reviewed SHA: `dc04d193185324f6913cde8efc40f4b238047dd8`; tree: `48690bfe3531d5095dc5c188f0fa26e62544f66e`.
- Independent clean worktree: `D:/wt/r07-pub-recheck1`, branch `codex/r07-publication-recheck1`, created directly from that SHA. Source/test working diffs remained empty.
- First review remains unchanged at [G-C-R07-publication-review-1.md](D:/wt/r07-pub-review1/reports/reviews/recovery/G-C-R07-publication-review-1.md), reviewed SHA `71e594cb958bd93d21fb7ed66574b3cba4cc47e1`.
- Material baseline `ad2158258e1107ed68fed4287d7da85cd6e9163f`; combination commits: ACL/lock `33c02be4eee3a7e0e84e0186b4618e9d906147d0` from author code `a80408fb35addf35c04a91d255f20fb9a987423e`, CVSS `20fb98541f9cc9035a2a2dad31e676b2a122e161` from author code `2ba07cbfbdb5d24d0bf3214dcf522ddfce3ed184`, then dc04 readable-context publication.
- Re-read AGENTS, execution/recovery R07 and state/handoff, amended publication CR, T19/T21 and the affected frozen contracts. The other unchanged T19–T23 and plans03–06 were already read during the first review. Applied [Ponytail Review 5.2.0](C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md).
- Fresh `.venv` used the original lock through `uv sync --frozen --project backend`. Test resources came only from the authorized controlled PG service on port25432. The review database was `test_dianzi_r06_catalog_r07_pub_review2_20261016`, run ID `r06_catalog_r07_pub_review2_20261016`. Credentials were captured in memory/environment, never in command argv or this report. PG runs were sequential; each catalog test retained its UUID schema, actual-database validation and original connection/statement/lock timeouts.

## Directed finding results

1. **Parent ACL / empty failed attempt: closed.** [inputs.py:44](D:/wt/r07-pub-recheck1/backend/src/ai_intel/enrichment/inputs.py:44) checks all three parent scopes for the whole roster before the first object read at line202. [publication.py:360](D:/wt/r07-pub-recheck1/backend/src/ai_intel/enrichment/publication.py:360) rechecks permissions before reading a prior receipt, and current-input validation repeats that check.

   Independent tests revoke a later source, document or revision in a two-source event. All three denied loads perform zero object reads. Empty-candidate `FAILED` attempts and historical replay also reject each revoked parent. Fourteen full table-content snapshots, including pre-existing row values and epoch values, remain identical after those rejections. A positive test with all parents in the authenticated owner's tenant still loads and publishes. The original same-byte parent negatives also now pass.

2. **Source writer / publisher deadlock: closed with new real-PG instrumentation.** [publication.py:99](D:/wt/r07-pub-recheck1/backend/src/ai_intel/enrichment/publication.py:99) derives lock identities from PG associations, takes source advisory locks in sorted source-ID order, holds source rows `FOR SHARE`, then document/revision rows before publication-scope/event locks. The actual `persist_source_response → ensure_source_registration` writer already takes the same source lock. Its Git blob is unchanged; the first review's correction of the earlier mistaken “no source advisory” description remains valid.

   Four new independent cases cover writer-first/publisher-first and one/two sources, with the two-source loaded order reversed. The leader is paused after its real document-lock phase. `pg_locks` observes the follower waiting on the exact hashed source advisory key, and `pg_blocking_pids` identifies the leader. After release, observed phases are source → document → scope for each actor. Writer-first commits the source revision and rejects the old enrichment snapshot with no request-specific results; publisher-first commits both operations. No `40P01`, `55P03`, hidden retry or partial publication occurs in these four cases. Sorted actual source IDs are asserted.

   Publisher-first tests also replay the old request after the source update, returning reused historical IDs with all fourteen table snapshots unchanged. A new request using that old snapshot rejects without changing state. Old workflow results retain their original event version; remaining current old dimensions are stale, while the source writer's newly created CVSS dimension is current/unknown rather than stale. This does not claim throughput or general concurrency performance beyond the tested cases.

3. **CVSS authority scope: closed.** [signals.py:552](D:/wt/r07-pub-recheck1/backend/src/ai_intel/enrichment/signals.py:552) now compares `(target, standard_version, authority)`. Different agencies remain available in parallel, while different score/vector values from the same literal agency and standard remain conflict. Original values, source institutions, JSON leaf citations and scoring-authority assertions remain stored; no maximum/average/source-priority selection was introduced.

   The original independent real-source persistence → publication → event-detail controls now both pass: different-authority available and same-authority conflict. The new 32 unit/contract controls and two PG cases also pass. The author [CVSS migration CR](D:/wt/r07-cvss-scope/docs/decisions/CR-R07_cvss_authority_scope.md) identifies each old expectation corrected under explicit root authorization and preserves parameter counts, source citations and true-conflict controls. It changes synthetic development regression expectations that contradicted T19/T21; it does not alter gold, holdout, scoring denominators or thresholds. Historical conflicts are not rewritten in place.

No new Must or Should finding was confirmed in the directed combination review.

## Readable provenance and regression boundaries

The root's change relative to the ACL/lock author is exactly internal workflow payload schema1 → schema2 plus `context=loaded.context.model_dump(mode="json")` at [publication.py:351](D:/wt/r07-pub-recheck1/backend/src/ai_intel/enrichment/publication.py:351). Independent PG publication, a new session, and receipt-to-change lookup retain the explicit rule label, event ID, expected event version, all revision IDs and supported CVE IDs. Identical replay leaves all fourteen table contents unchanged; changing the rule label while reusing the same request identity raises an idempotency conflict with no mutation.

The amended CR says old workflow schema1 existed only in isolated tests before product integration; there is no production migration here. This review does not claim that an old schema1 workflow receipt can be replayed as schema2. The separate ClaimSubmission schema1/2 and empty-additional-source serialization contract is unchanged. The original 77 PG cases rechecked source pairing, bounded/hash-verified inputs, exact evidence, old formats, source-scoped model hypotheses, full-roster rejection, current/CAS, historic IDs, transaction/outbox behavior and concurrent duplicate requests on this new SHA.

The original independent two-source model-candidate positive case also passes on dc04: two declared source assertions and exact visible references are returned through `event_detail/read_evidence`. The claim stays `model_hypothesis/unverified`; its dimension stays pending with no supported claim IDs. That is candidate persistence and citation plumbing, not real-model semantic support.

## Actual commands and evidence

Exact argv, cwd, start/end `+08:00`, process exit, runner wall time, full logs and JUnit results are in `reports/runs/recovery_r07_publication_review1_recheck_20261016/`. The reproducible entry is `recheck_runner.py`; no DSN is placed in its argv. Counts below overlap and are not added into a claimed larger score. “Time” is pytest time.

| Run | Actual scope | Result | Time / exit |
|---|---|---|---|
| `unit_contract_234` | Original eight R07/R02 files plus CVSS authority unit/contract | 234 passed; 0 failed/error/skip | 3.73s / 0 |
| `integration_pg_95` | Original77 + ACL/lock15 + CVSS2 + provenance1, real PG | 95 passed; 0 failed/error/skip | 108.23s / 0 |
| `original_probe_unchanged_9` | Exact first-review probe bytes, nine instances | 8 passed, 1 failed; 0 error/skip | 27.09s / 1 |
| `independent_recheck` | First new instrumentation plus ACL/state/provenance controls | 15 passed, 2 failed; 0 error/skip | 31.47s / 1 |
| `independent_recheck_v2` | Separate corrected expectation; all17 instances preserved | 17 passed; 0 failed/error/skip | 26.78s / 0 |
| `security_pg_recheck` | Unmodified complete `tests/security`, own PG resources | 203 passed; 0 failed/error/skip | 62.27s / 0 |
| Static | Ruff/format for10 changed Python files; mypy `src` | All passed; mypy99 files | exits0 |

The original probe SHA256 is `ebfc4dc423c5cdd32972adbad6eb4a9c92def6fd28261affa91a68f0fd7b22c3`, identical to the first-review file and the authors' preserved copy. The old concurrency barrier requires its writer to wait for a publisher advisory lock before release; the repaired publisher instead correctly waits for the writer's source lock. Actual unchanged-probe output is writer `AssertionError`, publisher SQLSTATE `55P03`. It remains a failed run and is not renamed green. The new independent timing test is a separate file and proves actual PG waiting/order without that contradictory barrier.

The first new instrumentation's two failures occurred after all four lock, outcome, replay and no-mutation checks had passed. Its final assertion incorrectly required every current dimension to be stale after collection, including the freshly replaced CVSS result. Original v1 source/log/XML and all four lock observations are preserved. v2 keeps every case and all lock/state checks, and separately checks old versus new current results. This is a reviewer test-expectation error and correction, not a product fix or gold change. Both test versions remain in the new raw directory. Marker-registration and third-party deprecation warnings are recorded; no failure was changed to skip.

Full unit/contract/security with the original coverage gate, strict CPU/PDF timing diagnosis, frontend, e2e, live and manual were not rerun in this directed review. The first-review 1993-passed pure run and the author's earlier frozen71 PDF guard failure retain their own version/time boundaries. Neither is used as evidence that dc04 fixes that unrelated CPU/startup issue.

## Caller and material audit

Official WSL Ubuntu-22.04/root CBM CLI indexed only this worktree's `backend/src` under the independent project `r07_pub_review2_20261016`: 99 Python files, 1360 nodes, 7031 edges, no partial/unusable parse. Index/help/schema/architecture and fully qualified input/publisher/read/parent-lock/source-writer/registration traces were rerun. Default cache/asset exclusions were retained; no asset-inclusion override was requested, and reports/holdout/secrets were outside the indexed root. `rg` and source inspection checked graph heuristic/lambda gaps.

The actual source worker calls `ensure_source_registration` before both source response and catalog persistence. The direct source response entrypoint itself also registers/locks the source. Direct catalog persistence does not acquire publication-scope locks, so it does not create the old scope/document cycle. The existing GET event-detail route calls the reviewed read service. The enrichment loader and publisher still have no product worker/job/API-enqueue caller; new real-model and product entrypoint integration is outside this Ship scope.

Author materials were independently checked against frozen material commits:

- ACL/lock material `b0a5b64014f89a689b6b1efcdd21e791b454c12f`: raw manifest SHA256 `34aed164803763a0486366478b1856e6119a9104015398310b5b671d9b98f745`; all112 artifact hashes match.
- CVSS material `fde252955fd88f537b844b0414d08967d0b2d67a`: artifact manifest SHA256 `471616bf0d46c3a8bb386101c919ab322e380d12f0968f7df84abc98ab2d39a1`; all97 hashes match.
- Both manifests match their frozen Git blob bytes. Eight relevant author source/test blobs match dc04 exactly; the publication root delta is separately stored. Source response writer, catalog writer, revision service, event linker, knowledge publisher and read service all retain their frozen71 blob bytes. Detailed comparisons are in `author_material_audit.json`; author green conclusions were not used instead of the independent reruns.

Root's final combination material was then checked in another detached checkout, `D:/wt/r07-pub-matcheck1`, at `9e722c944cf83086ffd30ad24a708172c13da189`. All47 final entries match both checkout bytes and raw Git blob bytes. Its final manifest SHA256 is `adf134ab772ab8867322633bce990cfe47c008e5737f2ca45a851aed09cbb91e`; the final task report SHA256 is `f3a90b67536a27f5696741a80db70dd6900ed8c7fcb21649cb0b0a3f052f541a`. There is no source/test/lock/dependency diff from tested dc04. The added material/report and narrowly scoped `.gitattributes` changes were read; raw preservation and `cr-at-eol` apply only to this run/report, with no global source checking exemption.

The earlier uncommitted41-entry manifest `af4b3798…` and report `2c1245ef…`, which this reviewer initially checked, are preserved as v1 copies and remain exactly equal to those earlier bytes. They are not used as the final material hashes. The report's CRLF-diff error and repair helper's initial default-encoding error are retained in the final47-entry packet; neither changed tested source/tests or is counted as a business test failure. `root_final_material_audit.json` records the exact final checks and document/attribute delta, completed at `2026-10-16T04:18:03+08:00`.

The final evidence manifest binds this new report, command records, both instrument versions, unchanged original probe, lock observations, author material comparison and exact frozen source/test/lock Git blobs. Its SHA256 is in a separate sidecar to avoid a self-referential hash. It also records a scan against actual private connection values. Only this new report and its dedicated raw directory were written by the reviewer.

## State and handoff

Eight-layer verification for this slice: unit passed; contract passed; integration passed in the stated original95 and independent17 scope; security passed in the complete203 regression plus new ACL cases; frontend not_run; e2e not_run; live not_run; manual not_run. Retained old-instrument failures are explicitly explained above. No source/model/paid API, third-party asset, real asset or PoC execution was performed. Throughput, maximum-size performance, accuracy, recall, costs and live duration are not claimed.

Evidence supports the stated F2/P2/R1 publication behavior and E1 scope/transaction boundaries only. There is no change to official score, gold, denominator or original whole-card requirements. The next bounded work is product job/worker/API integration and remaining genuine nine-dimensional/model/live behavior, followed by its own frozen independent review. The implementer/root may register this limited review result; this reviewer does not set accepted.

Verdict: Ship for the frozen publication service slice only. Original three Must findings closed; whole R07 and G-C remain unsigned.

Not checked: whole-card nine-dimensional automation, new authenticated HTTP/browser flow, enrichment worker/job enqueue/recovery, real-model/external-source support, frontend/e2e/live/manual, production schema1 workflow migration, throughput/score acceptance and the earlier CPU/PDF failure cause.
