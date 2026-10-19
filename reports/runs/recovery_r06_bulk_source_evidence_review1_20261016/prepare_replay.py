"""Reuse the frozen diagnostic instrumentation and exact OwnedJob wrapper."""

import hashlib
import json
from pathlib import Path

RUN = Path(__file__).resolve().parent
source = Path("D:/wt/r06-release-pg-diagnosis/reports/runs/recovery_r06_large_release_pg_diagnosis_20261016/replay.py")
original = source.read_text(encoding="utf-8")
candidate = original.replace("test_dianzi_r06_catalog_release_diag_", "test_dianzi_r06_catalog_bulk_review1_").replace("r06-large-release-pg-diagnosis-20261016", "r06-bulk-source-evidence-review1-20261016")
candidate = candidate.replace('"max_wall_seconds": 0.0})\nnetwork', '"max_wall_seconds": 0.0, "executemany_calls": 0, "parameter_rows": 0})\nnetwork')
candidate = candidate.replace('metric["count"] += 1\n    metric["wall_seconds"]', 'metric["count"] += 1\n    if executemany:\n        metric["executemany_calls"] += 1\n        metric["parameter_rows"] += len(parameters)\n    metric["wall_seconds"]')
candidate = candidate.replace('revisions.add_text_block, revisions.attach_evidence_span, executor.complete_job', 'revisions.register_source_revision_blocks, revisions.add_text_block, revisions.attach_evidence_span, executor.complete_job')
candidate = candidate.replace('elif label == "add_text_block":', 'elif label == "register_source_revision_blocks":\n                progress["blocks_saved"] += len(result)\n                progress["evidence_saved"] += len(result)\n            elif label == "add_text_block":')
start = candidate.index('spec = importlib.util.spec_from_file_location')
end = candidate.index('\n\n\ndef sql_shape', start)
limits_block = candidate[start:end]
candidate = candidate[:start] + candidate[end:]
candidate = candidate.replace('engine = build_engine(ApplicationSettings(app_env="test", database_url=URL))', limits_block + '\n\nengine = build_engine(ApplicationSettings(app_env="test", database_url=URL))')
candidate = candidate.replace('stop_sampler.set()\nsampler.join(timeout=5)', 'operation_sql_stats = json.loads(json.dumps(sql_stats))\nstop_sampler.set()\nsampler.join(timeout=5)')
candidate = candidate.replace('sample_engine.dispose()\nengine.dispose()', 'from verify_raw import verify\nwith engine.connect() as connection:\n    connection.execute(text("SET TRANSACTION READ ONLY"))\n    independent_comparison = verify(connection, store, BODY, DIGEST)\nassert outcome == "succeeded" and execute_wall < 35\nassert counts["documents"] == counts["revisions"] == 20\nassert counts["text_blocks"] == counts["evidence"] == 11827\nassert counts["page_receipts"] == counts["response_receipts"] == 1\nassert counts["outbox"] == 1 and counts["fetch_attempts"] == 1\nassert counts["content_objects"] == 21 and invalid_evidence == 0\nassert job["status"] == "succeeded" and job["error_code"] is None\nassert len(cursors) == 1 and cursors[0]["generation"] == cursors[0]["last_successful_page"] == 1\nassert cursors[0]["lease_owner"] is None and cursors[0]["lease_expires_at"] is None\nassert network == {"fixture_fetch_calls": 1, "http_transport_calls": 0, "nonlocal_socket_attempts": 0}\nsample_engine.dispose()\nengine.dispose()')
candidate = candidate.replace('"stages": dict(stages), "sql_shapes": dict(sql_stats), "sql_count": sum(value["count"] for value in sql_stats.values()),', '"stages": dict(stages), "sql_shapes": operation_sql_stats, "sql_count": sum(value["count"] for value in operation_sql_stats.values()),\n      "sql_metric_scope": "SQLAlchemy driver cursor calls through execute_job commit; executemany row executions are not PostgreSQL physical statement counts", "independent_comparison": independent_comparison,')
candidate = candidate.replace('"sql_wall_seconds": sum(value["wall_seconds"] for value in sql_stats.values())', '"sql_wall_seconds": sum(value["wall_seconds"] for value in operation_sql_stats.values())')
candidate = candidate.replace('assert verified_objects', 'assert verified_objects')
compile(candidate, str(RUN / "replay.py"), "exec")
(RUN / "replay.py").write_text(candidate, encoding="utf-8")
(RUN / "replay_instrument_provenance.json").write_text(json.dumps({"source_path": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "derived_replay_sha256": hashlib.sha256((RUN / "replay.py").read_bytes()).hexdigest(), "resource_changes": "OwnedJob exact module retained; apply before engine and forward migration so all replay instrumentation remains capped", "input_and_handler": "new private database, own ContentStore and fixed raw fixture; actual execute_job retained", "assertion_scope": "independent verify_raw.py checks every original leaf/row"}, indent=2), encoding="utf-8")
print("replay prepared; syntax checked; no handler invoked")
