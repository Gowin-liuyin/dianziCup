# G-C R06 document read API — independent review 1

What this change does: It adds authenticated public document lists, revision history, and evidence pages at `/v1` and `/api/v1`. Each read locks the PostgreSQL session and user in the same transaction as the document query, then returns saved source facts through the frozen DTOs.

Looks good. Ship **this document GET slice** at `49ee33f6a95099be619a59ff47c621713a089137`.

Review status: `awaiting_review`; independent slice verdict: `Ship`. This report does not change any task to `accepted`.

## Frozen scope and authority

- Reviewer: `/root/r06_document_api_independent_review`, a new non-author reviewer. Report first written: `2026-10-15T20:39:53+08:00` (actual file creation time); sealed time is recorded in the raw artifact receipts.
- Baseline: `71e852ce4be147d30aa1bc824bf18afda99fb332`. Product: `49ee33f6a95099be619a59ff47c621713a089137`. Detached review worktree: `D:/wt/r06-document-api-review` at metadata freeze `72eb1c0235805facd7f41310e5af5a110d0e0bad`.
- Six reviewed code/test files: `api/app.py`, `api/document_read_service.py`, `api/document_routes.py`, `api/knowledge_read_service.py`, `tests/integration/test_r06_document_api_pg.py`, and `tests/unit/test_r06_document_cursor.py`, under `backend/`. The product diff is 864 additions and two deletions. The metadata freeze adds only the author report, raw run files, and scoped byte-preservation attributes. `source_manifest.json` independently confirms all six product blobs match the frozen checkout.
- Read: repository `AGENTS.md`, execution map, current progress and handoff, recovery R06/R09 cards, T41, data/API/testing contracts 03/05/06, T41's referenced workflow contract, `CR-R04-R06_document_read_api.md`, `document_contracts.py`, and the author report. Applied the installed Ponytail 5.2.0 review skill. The author report was evidence to inspect, not the review verdict.
- Only this report and `reports/runs/recovery_r06_document_api_review_1_20261015/` were written. No product, migration, old test, threshold, gold label, dependency lock, or progress file changed. No push, public schema migration, database downgrade, or paid/model/source call was made.

## Findings

No concrete Must fix, Should fix, or Nice to have finding remains in the reviewed slice. The tests and source checks below support that verdict. They do not establish production load capacity or source live availability.

## Checked behavior

| Area | Independent evidence and result |
|---|---|
| Default app and both prefixes | New probes omit `auth_service` when calling `create_application`, so it builds the normal PostgreSQL authentication service. A real login Cookie opens list/detail/history on both prefixes; no Cookie returns 401. The engine is substituted only to select the isolated real PG schema. |
| Public-only permissions | Source, document, and revision visibility each hide list/detail/history, including from the same-tenant administrator. `asset_inventory` is excluded. Private evidence is excluded from both text and count; no public evidence returns an explicit note rather than a risk conclusion. Original nested-ACL PG regressions also pass. |
| Revocation and races | Original pre-lock revocation returns 401. Independent tenant change between initial authentication and the PG lock returns 403. A concurrent logout started after the read lock cannot finish until the read releases its transaction; the authorized read completes, and the next request is 401. Locks therefore establish a visible ordering. |
| History, dates, and fixed pages | Original PG tests retain old titles, raw calendar dates and null precise timestamps, legacy title/coverage unknowns, history pagination, and foreign-revision 404. Independent read-page → publish later revision → read the saved revision's next page keeps the old title, revision ID, quote hash, and `is_current=false`. |
| Cursor and filters | Pure cursor tests cover round trips, invalid payloads and duplicate keys. Independent HTTP probes reject duplicate JSON keys and changes to q/kind/category with 422; literal title search does not turn `%` or `_` into wildcards. |
| Evidence integrity | Original and independent PG tests reject altered quote/hash, shifted Unicode coordinates, and a mismatched block with 503 without the hidden source text. Existing R04 corrupt-evidence regressions are rerun under the review's own schema. |
| Metadata, URL, HTML | Only contracted metadata fields are projected; arbitrary metadata is absent. Original HTML-title/notes tests retain JSON text without executing it. Independent invalid HTTP/userinfo/fragment/sensitive-query URLs, unsupported date precision, overlong notes, and unsafe license links return 503 without leaking stored values. No source URL is fetched by these routes. |
| Empty and unavailable | An unmatched title filter returns 200 with empty items and null cursor. Missing resources are 404. Malformed stored facts are 503. Unconfigured document DB is 503, not a successful empty list. |
| Bounds and query shape | SQL returns at most `limit+1` list/history rows and one bounded evidence page, with a separate revision-scoped count. The independent detail request uses no more than ten SQL statements and exactly one evidence/block query with LIMIT. More than 2000 public spans returns 503. This is a small isolated workload check, not a p95/load benchmark. |
| Shared query compatibility | `_evidence_rows` keeps default `public_only=false` and `limit=None`; original callers remain unchanged. An independent real-PG probe confirms 108 rows remain uncapped and same-tenant private `read_evidence` stays available to its existing administrator caller, while the new public evidence method returns 100 of 107 public rows. Original R04 event/evidence, nested-ACL, legacy-locator and corrupt-evidence cases pass. |

CBM 0.11.0 was run from the specified official WSL binary with the review's own cache and project. The index covers **only** this worktree's `backend/src`: 1206 nodes, 5910 edges, zero unindexed/skipped/partial/unusable files. Independent traces cover `create_application`, document router, authentication lock, public revision evidence, and shared evidence query; `rg` independently verifies the direct callers. The shared trace includes event detail/read evidence and downstream answering/retrieval paths. The nested route `serve` callback and its transaction were also read in source because a static trace alone does not prove the runtime lock.

## Actual commands and results

All times below are actual seconds in `+08:00`. Cwd is `D:/wt/r06-document-api-review/backend` unless shown otherwise. The full absolute interpreter path, argv, JUnit path, code identity, cwd, and seconds are in each `.command.json`; log/XML names share the row's label.

| Label / actual command | Start → end (+08:00, 2026-10-15) | Exit | Result |
|---|---|---:|---|
| `sync`: `uv sync --frozen --extra semantic` | 20:31:39 → 20:31:47 | 0 | Own Python 3.12.13 venv created; editable package points to this worktree. Cache hardlink fallback warning only. |
| `pure`: own `.venv/Scripts/python.exe -m pytest tests/unit tests/contract tests/security -m "not real_pg" -q --junitxml=…/pure.xml` | 20:32:27 → 20:33:52 | 0 | 1687 passed; 10 real_pg deselected; zero skipped; 74.74% against unchanged 60% coverage gate; pytest 78.53s. No DB environment. Includes the original nine document cursor cases. |
| `pg`: own Python `-m pytest tests/integration/test_r06_document_api_pg.py --no-cov -q --junitxml=…/pg.xml` | 20:32:30 → 20:32:52 | 0 | 20 passed; zero skipped; pytest 19.73s. |
| `probe`: own Python `-m pytest <run>/test_independent_probes.py --no-cov -q --import-mode=importlib -p conftest --junitxml=…/probe.xml` | 20:34:29 → 20:34:50 | 0 | Initial 23 passed. Retained raw; superseded by the expanded run, not added to its count. |
| `probe_v2`: same probe command, final test source and `probe_v2.xml` | 20:36:29 → 20:37:01 | 0 | 31 passed; zero skipped; pytest 29.82s. Includes six existing R04 regression cases and two new query/bound probes. |
| `ruff`: own Python `-m ruff check src tests` | 20:32:28 → 20:32:28 | 0 | All checks passed. |
| `mypy`: own Python `-m mypy src` | 20:32:28 → 20:32:39 | 0 | 91 source files, no issues. |
| `format`: own Python `-m ruff format --check src tests` | 20:35:23 → 20:35:23 | 0 | 211 files already formatted. |
| `diff`: `git diff --check <baseline> <product>`; cwd review root | 20:35:26 → 20:35:26 | 0 | No whitespace errors. |
| `cbm_index`: WSL official binary `cli --json index_repository --repo-path /mnt/d/wt/r06-document-api-review/backend/src --name dianzi-r06-document-api-review-72eb1c --mode fast` | 20:32:09 → 20:32:14 | 0 | Independent source-only graph; five trace commands also exit 0, exact receipts retained. |

The PG run and probes use only `test_dianzi_r06_catalog_document_review_20261015`, with exact `DIANZI_TEST_RUN_ID=r06_catalog_document_review_20261015`. The private localhost base connection was read in process from the authorized WSL connection file and never printed or stored in the reports. Each test uses `test_r06_catalog_documents_pg.catalog_engine` and its fresh UUID schema; cleanup drops only that test schema. The original R04 functions receive this fixture, not the R04 database fixture. No continuous-collection database was connected.

Read-only `public` snapshots before and after each PG run are identical: `public_counts={}`, `public_versions=[]`. Migrations occurred in UUID schemas, not `public`. These snapshots verify the dedicated review database's public namespace; they make no claim about another database.

All pytest runs show one installed Starlette TestClient deprecation warning. There was no test failure, skipped test, changed expectation, lowered gate, business-code fix, or second source tree in this review. The author's historical double-source coverage failure was not overwritten or reclassified.

## Delivery and limits

Raw evidence is in `reports/runs/recovery_r06_document_api_review_1_20261015/`: command receipts, full stdout/logs and JUnit, independent probe source, CBM output, source/diff checks, public before/after snapshots, and SHA-256 byte manifest. `artifact_manifest.json` lists the delivered raw files and excludes itself; `source_manifest.json` freezes the six reviewed product identities. Root may add scoped byte-preservation Git attributes when archiving, but this reviewer did not change `.gitattributes`.

Score evidence is limited to F1/F2/F3/E1/T41-C03/C04/C06 data-read support: public saved documents, correct saved revision and source time, verified evidence, and authentication/permission boundaries. It does not establish a complete source category, continuous monitoring result, knowledge card, answer accuracy, official performance score, or whole T41/R06/R09/R17 acceptance.

Next task suggestion: the controller can use this slice verdict when wiring the bounded new-source worker and real API/browser document workflow. Keep the separate frontend review, live source evidence, full-card requirements, and stage checkpoint open.

Verdict: Ship this frozen document GET slice.

Not checked: real-source worker ingestion/live browser E2E, full R06/R09/R17 acceptance, high-load latency/performance, model-backed question generation/retrieval execution, full session lifetime boundaries already defined by the unchanged authentication contract, or official evaluation/continuous-running metrics.
