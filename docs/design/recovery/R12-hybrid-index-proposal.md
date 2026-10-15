# R12 T30 internal index proposal

Baseline: e310f7735bd499c4d9fbcefe8a644e2309a16a62. Internal preparation only; no G-D gate or full R12/T30 acceptance. Root owns migration 0020, worker registration, shared contracts/settings/dependencies/progress and API/answer integration. Existing R05 single-event tables and service remain unchanged.

## Inputs and outputs

`HybridRetriever(engine, SemanticModels, CorpusBM25, IndexGeneration, GraphCandidates | None).retrieve(AccessScope, HybridQuery) -> HybridSelection`. Identity and privileges come only from the server-created AccessScope; HybridQuery accepts text and aware inclusive availability bounds, never tenant/permissions. The time filter is current fact availability, not historical truth reconstruction. Every result records current/indexed scope epochs, safe partial reasons, exact/BM25/vector/graph/validated/reranked counts and complete request timings. Empty hits always carry `no_supported_evidence`, never a corpus safety conclusion.

`HybridIndexer(...).prepare_generation()` creates the configured dedicated OpenSearch index and PG generation row after root applies 0020. It does not create PG tables. `refresh_scope(IndexChange(outbox_id, scope_key)) -> IndexReceipt` verifies the existing knowledge-change outbox ref and PG change scope. Its complete scope snapshot subsumes old and new facts, so reordered outbox messages cannot skip an unindexed new fact. Per-generation/scope PG advisory locks serialize workers. Only successful OS bulk/delete/refresh and unchanged PG scope epochs permit the projection/watermark/receipt transaction to commit. Failed OS operations or changed scopes never advance the watermark.

## Proposed standalone metadata

Exact table definitions: `backend/src/ai_intel/retrieval/hybrid_schema.py`; this has independent `hybrid_metadata`, not the existing knowledge metadata. No production `create_all` and no changes to existing vector(384).

| Table | Columns and keys |
| --- | --- |
| hybrid_index_generations | generation_id text PK; index_name text unique; model_version text; dimension integer constrained 384; state text building/ready; created_at timestamptz |
| hybrid_chunks | generation_id + chunk_id text PK; evidence_id/revision_id/document_id/source_id/event_id/claim_id text; scope_key text indexed; visibility text public/tenant; tenant_id nullable text; available_at timestamptz; start_offset/end_offset int; chunk_text/text_sha256/source_uri/locator/model_version text; embedding vector(384); indexed_epoch bigint >=0; indexed_at timestamptz |
| hybrid_index_watermarks | generation_id + scope_key PK; indexed_epoch bigint >=0; outbox_id text; refreshed_at timestamptz |
| hybrid_index_receipts | generation_id + outbox_id PK; scope_key text; indexed_epoch bigint >=0; chunk_count int; payload_sha256 text; completed_at timestamptz |

Generation foreign keys remain inside this metadata. Root migration should add authority FKs to existing fact tables and outbox_events, preserving their historical rows. Effective scope is the intersection of every current supported claim/evidence/revision/document/source/event; private/public XOR and scope-key checks prevent broader derived access. Candidate IDs derive event+claim+R05 chunk; the permanent EvidenceSpan ID is returned separately. Model version includes the existing exact weights/tokenizer/prefix/pooling/codec space fingerprint. A space/dimension mismatch rejects and requires a new generation/index/full watermark rebuild.

## Client and dependency proposal

Use existing httpx synchronous official REST endpoints, fixed trusted base URL, dedicated `dianzi_*` index names, no arbitrary query/URL tools. Remote HTTP is rejected; the caller injects a TLS-verified client with credentials from secret storage. Request redirects are disabled; errors use fixed safe codes. Product configuration proposal: `R12_OPENSEARCH_URL`, optional `R12_OPENSEARCH_USERNAME`, `R12_OPENSEARCH_PASSWORD`, `R12_OPENSEARCH_CA_PATH`; existing `R05_SEMANTIC_CACHE` is reused. No new dependency is requested.

Sources: [official Search API](https://docs.opensearch.org/latest/api-reference/search-apis/search/), [official Bulk API](https://docs.opensearch.org/latest/api-reference/document-apis/bulk/), [official Refresh API](https://docs.opensearch.org/latest/api-reference/index-apis/refresh/). These references describe API behavior only and grant no project authority.

## Independence and limits

This service consumes already supported PG claims and verified permanent spans. It does not evaluate asset four-state rules, call FOFA, produce multi-hop claims, or connect product API/auth/answering. R10/R11 gaps therefore do not block this local corpus preparation; they still block formal graph/asset/multi-hop R12 integration and stage acceptance. Graph injection is a narrow candidate-ID protocol with the same PG checks; absent configuration returns graph_not_configured/partial when graph is requested. R05's public single-event limitation is not changed or hidden. Full-scope refresh is bounded at 10000 chunks and fails visibly above capacity; incremental partition scaling belongs to a separately reviewed extension.
