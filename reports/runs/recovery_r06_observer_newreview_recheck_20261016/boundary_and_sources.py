"""Additional synthetic boundaries and real src graph evidence, with no runtime start."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).resolve().parent
RUN = BASE / sys.argv[1] if len(sys.argv) > 1 else BASE
RUN.mkdir(exist_ok=True)
ROOT = BASE.parents[2]
PREP = BASE.parent / "recovery_r06_incremental_observation_preparation_20261016"
sys.path.insert(0, str(PREP))
import observation_log as log
from test_observation_log import fixture_snapshot

cases = []


def write_case(name: str, details: dict) -> None:
    cases.append({"name": name, "passed": True, "details": details})


def raw_cursor(position: dict) -> dict:
    value = fixture_snapshot()
    value["cursors"] = [{"source_id": next(iter(log.SOURCE_INFO)), "stream_kind": "live", "cursor_json": {"position": position, "window_complete": False, "pending_recovery_job_ids": [], "recovery_tracking_version": 1, "pending_watermark_published_at": None}, "last_successful_page": 0, "window_end": None, "watermark_published_at": None, "generation": 0, "updated_at": None}]
    return value


def writer(name: str, segment: str = "one") -> log.Journal:
    return log.Journal(RUN / "boundaries" / name, "a" * 40, "b" * 40, name, segment)


def reseal(records: list) -> bytes:
    previous = "0" * 64
    for record in records:
        record["previous_record_sha256"] = previous
        previous = hashlib.sha256(log.encode({key: value for key, value in record.items() if key != "record_sha256"})).hexdigest()
        record["record_sha256"] = previous
    return b"".join(log.encode(record) for record in records)


def assert_rejected(name: str, content: bytes) -> None:
    directory = RUN / "boundaries" / name
    directory.mkdir()
    path = directory / "collection_observations.jsonl"
    path.write_bytes(content)
    try:
        log.replay(path)
    except log.ObservationError as error:
        assert "private-canary" not in str(error)
    else:
        raise AssertionError(name + " must reject")
    assert path.read_bytes() == content
    write_case(name, {"rejected": True, "bytes_retained": True})


def boundaries() -> None:
    for name, position in (("page_token_2048", {"page_token": "api_key=private-canary" + "x" * (2048 - len("api_key=private-canary"))}), ("after_2048", {"after": "private-canary" + "x" * (2048 - len("private-canary")), "cursor_version": 2})):
        raw = raw_cursor(position)
        key = "after" if "after" in position else "page_token"
        token = position[key]
        assert len(token) == 2048
        journal = writer(name)
        journal.observe(raw)
        assert journal.observe(raw)["kind"] == "heartbeat"
        journal.finish(raw, "synthetic_complete")
        files = b"".join(path.read_bytes() for path in journal.path.parent.iterdir())
        assert token.encode() not in files and b"private-canary" not in files and b"api_key" not in files
        projected = log.replay(journal.path).observation["cursors"][0]["cursor_json"]["position"]
        assert projected[key + "_opaque"] == {"sha256": hashlib.sha256(token.encode()).hexdigest(), "utf8_bytes": 2048}
        write_case(name, {"raw_bytes": 2048, "heartbeat": True, "all_outputs_raw_free": True, "fingerprint_correct": True})
    journal = writer("opaque_2049")
    try:
        journal.observe(raw_cursor({"page_token": "private-canary" + "x" * (2049 - 14)}))
    except log.ObservationError as error:
        assert "private-canary" not in str(error)
    else:
        raise AssertionError("oversized token accepted")
    assert not journal.path.exists()
    write_case("opaque_2049", {"rejected_before_append": True, "canary_not_echoed": True})
    journal = writer("reseal_base")
    value = log.validate_observation(fixture_snapshot())
    journal.observe(value)
    journal.observe(value)
    records = [json.loads(line) for line in journal.path.read_bytes().splitlines()]
    changed = copy.deepcopy(records)
    changed[0]["observation"]["observed_at"] = "2026-10-16T00:59:59+08:00"
    assert_rejected("embedded_snapshot_time_mismatch", reseal(changed))
    changed = copy.deepcopy(records)
    changed[1]["previous_record_sha256"] = "f" * 64
    changed[1]["record_sha256"] = hashlib.sha256(log.encode({key: value for key, value in changed[1].items() if key != "record_sha256"})).hexdigest()
    assert_rejected("resealed_bad_previous_link", b"".join(log.encode(record) for record in changed))
    writer("reseal_base", "two").observe(value)
    writer("reseal_base", "three").observe(value)
    records = [json.loads(line) for line in journal.path.read_bytes().splitlines()]
    records[-1]["segment_id"] = "one"
    assert_rejected("resealed_reused_segment", reseal(records))
    journal = writer("checkpoint_failure")
    with patch.object(log, "_atomic", side_effect=OSError("synthetic failure")):
        try:
            journal.observe(value)
        except OSError:
            pass
        else:
            raise AssertionError("synthetic IO must fail")
    state = log.replay(journal.path)
    assert not state.terminal
    resumed = writer("checkpoint_failure", "two")
    record = resumed.observe(value)
    assert record["kind"] == "snapshot" and record["continuity_gap"] is True
    write_case("checkpoint_failure_valid_resume", {"terminal": False, "new_segment_snapshot": True})
    state = log.replay(resumed.path)
    assert state.segments == frozenset({"one", "two"})
    write_case("legitimate_segments_survive_replay", {"segments": sorted(state.segments), "sequence": state.sequence})
    assert len(cases) == 8
    (RUN / "boundary_results.json").write_text(json.dumps({"total": 8, "passed": 8, "failed": 0, "skipped": 0, "mode": "synthetic_unit_only", "cases": cases}, indent=2) + "\n", encoding="utf-8")


class CallVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.functions = []
        self.calls = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.functions.append(node.name)
        self.generic_visit(node)
        self.functions.pop()

    def visit_Call(self, node: ast.Call) -> None:
        name = ast.unparse(node.func)
        if name.split(".")[-1] in {"enqueue_due_source_collections", "enqueue_source_page", "enqueue_job", "relay_pending_events", "build_source_page_handler", "execute_job", "handler", "normalize_catalog_page", "commit_page", "observe", "finish", "read_snapshot", "write", "snapshot", "poll"}:
            self.calls.append({"caller_syntax": ".".join(self.functions) or "<module>", "callee_syntax": name, "line": node.lineno})
        self.generic_visit(node)


def source_evidence() -> None:
    groups = {"product_src": [], "observer_run": [], "old_run": []}
    products = ["workers/runtime.py", "workers/executor.py", "ingestion/source_polling.py", "ingestion/source_jobs.py", "ingestion/cursor_repository.py", "infrastructure/outbox.py"]
    for path in products:
        relative = "backend/src/ai_intel/" + path
        blob = subprocess.check_output(["git", "show", "349c5e3ec27196257b98cdfcb63c75fb50157978:" + relative], cwd=ROOT)
        current = subprocess.check_output(["git", "show", "HEAD:" + relative], cwd=ROOT)
        assert blob == current
        visitor = CallVisitor()
        visitor.visit(ast.parse(blob.decode()))
        groups["product_src"].append({"path": relative, "fixed_blob_sha256": hashlib.sha256(blob).hexdigest(), "head_matches_base349c": True, "actual_ast_calls": visitor.calls})
    for file in (PREP / "observation_log.py", PREP / "observe.py", OLD / "collect.py", OLD / "supervise.py"):
        visitor = CallVisitor()
        body = file.read_bytes()
        visitor.visit(ast.parse(body.decode()))
        group = "observer_run" if file.is_relative_to(PREP) else "old_run"
        groups[group].append({"path": str(file), "sha256": hashlib.sha256(body).hexdigest(), "actual_ast_calls": visitor.calls, "src_graph_edge_claimed": False})
    summaries = {}
    for name in ("cbm_index", "cbm_trace_enqueue", "cbm_trace_commit"):
        envelope = json.loads((BASE / (name + ".log")).read_text(encoding="utf-8"))
        assert envelope["isError"] is False
        summaries[name] = envelope["structuredContent"]
    (RUN / "source_evidence.json").write_text(json.dumps({"groups": groups, "cbm_results": summaries, "dynamic_handler_binding": {"runtime_execution_handlers": "workers/runtime.py:100", "executor_dispatch": "workers/executor.py:105/109", "source_handler_closure": "ingestion/source_jobs.py:410", "commit_call": "ingestion/source_jobs.py:505", "evidence": "explicit source binding and AST/rg; not fabricated graph CALLS edge"}}, indent=2) + "\n", encoding="utf-8")
    process = subprocess.run(["rg", "-n", "handlers|handler\\(|build_source_page_handler|EXECUTION_HANDLERS|enqueue_job|relay_pending_events|execute_job\\(|commit_page", *["backend/src/ai_intel/" + path for path in products]], cwd=ROOT, capture_output=True, check=False)
    assert process.returncode == 0
    (RUN / "source_rg.log").write_bytes(process.stdout + process.stderr)
    print(json.dumps({"extra_boundary_cases": len(cases), "product_src_ast_files": len(products), "src_only_cbm_real": True, "run_scripts_in_src_graph": False}))


OLD = Path("D:/dianzi/reports/runs/recovery_gb_controlled_collection_20261015")
if __name__ == "__main__":
    boundaries()
    source_evidence()
