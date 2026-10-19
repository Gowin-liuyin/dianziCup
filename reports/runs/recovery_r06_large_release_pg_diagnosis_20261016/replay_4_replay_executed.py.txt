"""Real-byte offline replay through unchanged handler, PG, CAS, receipt and cursor paths."""

import functools
import ctypes
import hashlib
import importlib.util
import json
import os
import re
import socket
import sys
import threading
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from control import ROOT, RUN, SHA, now, write
from ai_intel.infrastructure.database import build_engine, run_migrations
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.network import FetchResult, NetworkGateway
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.ingestion import catalog_documents, catalog_pages, source_jobs
from ai_intel.ingestion.cursor_repository import SourceCursorRepository
from ai_intel.ingestion.source_failure_receipts import SourceResponseRecorder
from ai_intel.knowledge import revisions
from ai_intel.workers import executor

NUMBER = os.environ["DIAG_REPLAY_NUMBER"]
URL = os.environ.pop("DIAG_DATABASE_URL")
DATABASE = make_url(URL).database
assert DATABASE and DATABASE.startswith("test_dianzi_r06_catalog_release_diag_")
PREFIX = "replay_" + NUMBER
RAW = Path("D:/dianzi-local-evidence/recovery_r06_live_segment_8a_20261016/release_raw.bin")
DIGEST = "25e00623a07dcafe8d8d6b3535e400e078ef758e965742a37fe76d5186bb69f7"
BODY = RAW.read_bytes()
assert len(BODY) == 616865 and hashlib.sha256(BODY).hexdigest() == DIGEST
STARTED = now()
stages = defaultdict(lambda: {"calls": 0, "completed": 0, "wall_seconds": 0.0, "cpu_seconds": 0.0, "max_wall_seconds": 0.0})
sql_stats = defaultdict(lambda: {"count": 0, "wall_seconds": 0.0, "max_wall_seconds": 0.0})
network = {"fixture_fetch_calls": 0, "http_transport_calls": 0, "nonlocal_socket_attempts": 0}
progress = {"documents_saved": 0, "blocks_saved": 0, "evidence_saved": 0}
parsed_counts = {}
engine = build_engine(ApplicationSettings(app_env="test", database_url=URL))


def denied_http(*args, **kwargs):
    network["http_transport_calls"] += 1
    raise RuntimeError("offline_diagnosis_http_forbidden")


NetworkGateway.fetch = denied_http
NetworkGateway.post_json = denied_http
socket_connect = socket.socket.connect


def guarded_connect(self, address):
    if not isinstance(address, tuple) or address[0] not in {"127.0.0.1", "localhost", "::1"} or address[1] != 25432:
        network["nonlocal_socket_attempts"] += 1
        raise RuntimeError("offline_diagnosis_nonlocal_socket_forbidden")
    return socket_connect(self, address)


socket.socket.connect = guarded_connect
run_migrations(URL, "0016_source_response_receipts")
with engine.connect() as connection:
    assert connection.scalar(text("select current_database()")) == DATABASE
    assert connection.scalar(text("select version_num from alembic_version")) == "0016_source_response_receipts"

spec = importlib.util.spec_from_file_location("original_runtime_limits", "D:/dianzi/reports/runs/recovery_r06_live_segment_8a_20261016/runtime_limits.py")
limits = importlib.util.module_from_spec(spec)
spec.loader.exec_module(limits)
owned_job = limits.OwnedJob()
process_created = ctypes.c_ulonglong()
process_exited = ctypes.c_ulonglong()
process_kernel = ctypes.c_ulonglong()
process_user = ctypes.c_ulonglong()
owned_job.kernel.GetProcessTimes.argtypes = [limits.wintypes.HANDLE] + [ctypes.POINTER(ctypes.c_ulonglong)] * 4
owned_job.kernel.GetProcessTimes.restype = limits.wintypes.BOOL
assert owned_job.kernel.GetProcessTimes(owned_job.kernel.GetCurrentProcess(), ctypes.byref(process_created), ctypes.byref(process_exited), ctypes.byref(process_kernel), ctypes.byref(process_user))
identity = {"pid": os.getpid(), "creation_time_epoch": (process_created.value - 116444736000000000) / 10000000, "database": DATABASE,
            "cpu_rate": limits.CPU_RATE, "memory_per_process": limits.MEMORY_PER_PROCESS, "memory_total": limits.MEMORY_TOTAL,
            "original_limit_module_sha256": hashlib.sha256(Path(spec.origin).read_bytes()).hexdigest()}
write(PREFIX + "_process_identity.json", identity)


def sql_shape(statement):
    verb = statement.lstrip().split(None, 1)[0].upper()
    match = re.search(r"(?:FROM|INTO|UPDATE)\s+([a-z_][a-z_0-9]*)", statement, re.I)
    table = match.group(1).lower() if match else "none"
    if "pg_advisory_xact_lock" in statement:
        table = "advisory_lock"
    return verb + ":" + table


@event.listens_for(engine, "before_cursor_execute")
def before_sql(connection, cursor, statement, parameters, context, executemany):
    context.diag_started = time.perf_counter()
    context.diag_shape = sql_shape(statement)


@event.listens_for(engine, "after_cursor_execute")
def after_sql(connection, cursor, statement, parameters, context, executemany):
    wall = time.perf_counter() - context.diag_started
    metric = sql_stats[context.diag_shape]
    metric["count"] += 1
    metric["wall_seconds"] += wall
    metric["max_wall_seconds"] = max(metric["max_wall_seconds"], wall)


def wrap(function, label):
    @functools.wraps(function)
    def measured(*args, **kwargs):
        metric = stages[label]
        metric["calls"] += 1
        wall, cpu = time.perf_counter(), time.process_time()
        try:
            result = function(*args, **kwargs)
            metric["completed"] += 1
            if label == "normalize_catalog_page":
                parsed_counts.update({"pages": 1, "documents": len(result.documents),
                                      "blocks": sum(len(member.parsed.blocks) for member in result.documents),
                                      "planned_evidence": sum(len(member.parsed.blocks) for member in result.documents),
                                      "document_payload_bytes": sum(len(member.payload) for member in result.documents),
                                      "next_cursor_present": bool(result.next_cursor)})
            if label == "save_document_revision":
                progress["documents_saved"] += 1
            elif label == "add_text_block":
                progress["blocks_saved"] += 1
            elif label == "attach_evidence_span":
                progress["evidence_saved"] += 1
            return result
        finally:
            elapsed = time.perf_counter() - wall
            metric["wall_seconds"] += elapsed
            metric["cpu_seconds"] += time.process_time() - cpu
            metric["max_wall_seconds"] = max(metric["max_wall_seconds"], elapsed)
    return measured


for function in [source_jobs.ensure_source_registration, source_jobs._fetch_catalog_page, catalog_pages.normalize_catalog_page,
                 catalog_documents.persist_catalog_documents, revisions.register_response_content, revisions.save_document_revision,
                 revisions.add_text_block, revisions.attach_evidence_span, executor.complete_job]:
    original, measured = function, wrap(function, function.__name__)
    for module in tuple(sys.modules.values()):
        if module is not None and getattr(module, "__name__", "").startswith("ai_intel"):
            for name, value in tuple(vars(module).items()):
                if value is original:
                    setattr(module, name, measured)
for cls, names in [(SourceCursorRepository, ("claim", "commit_page", "release")), (SourceResponseRecorder, ("record_response", "mark_outcome")),
                   (ContentStore, ("store_bytes", "read_verified"))]:
    for name in names:
        setattr(cls, name, wrap(getattr(cls, name), cls.__name__ + "." + name))

store_root = Path("D:/dianzi-local-evidence/r06-large-release-pg-diagnosis-20261016") / DATABASE / "objects"
assert not store_root.exists()
store = ContentStore(store_root)


def fixture_fetch(url):
    assert url == "https://api.github.com/repos/ollama/ollama/releases?per_page=20&page=1"
    network["fixture_fetch_calls"] += 1
    return FetchResult(url, 200, "application/json", BODY, {})


request = source_jobs.SourcePageRequest(source_kind="ollama_releases", stream_kind="live",
                                       window_end=datetime(2026, 10, 15, 19, 0, tzinfo=UTC), remaining_pages=5)
with Session(engine) as session, session.begin():
    job_id = source_jobs.enqueue_source_page(session, request, datetime.now(UTC), idempotency_key="diag-" + uuid4().hex)
handler = source_jobs.build_source_page_handler(store, fetcher=fixture_fetch)
handler = wrap(handler, "collect_page")
stop_sampler = threading.Event()
samples = []
sample_engine = create_engine(make_url(URL), hide_parameters=True, connect_args={"connect_timeout": 3, "options": "-c statement_timeout=1000 -c default_transaction_read_only=on", "application_name": "r06_diag_sampler"})


def sample():
    while not stop_sampler.is_set():
        try:
            with sample_engine.connect() as connection:
                connection.execute(text("SET TRANSACTION READ ONLY"))
                states = [dict(row) for row in connection.execute(text("select pid,application_name,state,wait_event_type,wait_event,extract(epoch from now()-xact_start) transaction_age_seconds,pg_blocking_pids(pid) blocking_pids from pg_stat_activity where datname=current_database() and pid<>pg_backend_pid()")).mappings()]
                locks = [dict(row) for row in connection.execute(text("select locktype,granted,count(*) quantity from pg_locks where pid in(select pid from pg_stat_activity where datname=current_database() and pid<>pg_backend_pid()) group by locktype,granted")).mappings()]
            item = {"observed_at": now(), "pid": os.getpid(), "creation_time_epoch": identity["creation_time_epoch"],
                    "elapsed_seconds": time.perf_counter() - execute_started, "cpu_seconds": time.process_time() - cpu_started,
                    "usage": owned_job.usage(), "progress": dict(progress), "stages": dict(stages), "sql_count": sum(value["count"] for value in sql_stats.values()),
                    "states": states, "locks": locks}
            samples.append(item)
            with (RUN / (PREFIX + "_samples.jsonl")).open("a", encoding="utf-8") as output:
                output.write(json.dumps(item, default=str) + "\n")
        except Exception as error:
            with (RUN / (PREFIX + "_sampler_errors.jsonl")).open("a", encoding="utf-8") as output:
                output.write(json.dumps({"observed_at": now(), "error_type": type(error).__name__}) + "\n")
        stop_sampler.wait(0.5)


execute_started, cpu_started = time.perf_counter(), time.process_time()
write(PREFIX + "_execution_start.json", {"started_at": now(), "job_id": job_id, "database": DATABASE, "real_replay_ordinal": len(list(RUN.glob("replay_*_execution_start.json"))) + 1})
sampler = threading.Thread(target=sample, daemon=True)
sampler.start()
outcome = executor.execute_job(engine, job_id, "diag-" + NUMBER, {source_jobs.SOURCE_JOB_TYPE: handler})
execute_wall, execute_cpu = time.perf_counter() - execute_started, time.process_time() - cpu_started
stop_sampler.set()
sampler.join(timeout=5)
with engine.connect() as connection:
    connection.execute(text("SET TRANSACTION READ ONLY"))
    counts = dict(connection.execute(text("select (select count(*) from documents) documents,(select count(*) from document_revisions) revisions,(select count(*) from text_blocks) text_blocks,(select count(*) from evidence) evidence,(select count(*) from source_page_receipts) page_receipts,(select count(*) from source_response_receipts) response_receipts,(select count(*) from fetch_attempts) fetch_attempts,(select count(*) from content_objects) content_objects,(select count(*) from outbox_events) outbox")).mappings().one())
    job = dict(connection.execute(text("select status,error_code,started_at,finished_at,lease_expires_at from job_runs where job_id=:job"), {"job": job_id}).mappings().one())
    cursors = [dict(row) for row in connection.execute(text("select generation,last_successful_page,lease_owner,lease_expires_at from source_cursors")).mappings()]
    receipts = [dict(row) for row in connection.execute(text("select parse_outcome,response_content_hash,response_size_bytes from source_response_receipts")).mappings()]
    invalid_evidence = connection.scalar(text("select count(*) from evidence e join text_blocks b on e.block_id=b.block_id where e.quote<>substring(b.block_text from e.start_offset-b.start_offset+1 for e.end_offset-e.start_offset) or e.quote_sha256<>b.text_sha256 or e.verified_at is null"))
sample_engine.dispose()
engine.dispose()
verified_objects = 0
for path in store_root.glob("*/*"):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == path.name
    verified_objects += 1
write(PREFIX + "_result.json", {"started_at": STARTED, "ended_at": now(), "reviewed_sha": SHA, "database": DATABASE,
      "process_identity": identity, "job_id": job_id, "mode": "real original bytes offline fixture gateway plus real PG; not live",
      "raw_size_bytes": len(BODY), "raw_sha256": DIGEST, "header_scope": "original headers not persisted in receipt; explicit empty headers, terminal cursor fixture",
      "input_payload": request.model_dump(mode="json"), "parsed_counts": parsed_counts, "execute_wall_seconds": execute_wall, "execute_cpu_seconds": execute_cpu,
      "outcome": outcome, "job": job, "counts": counts, "cursors": cursors, "response_receipts": receipts,
      "stages": dict(stages), "sql_shapes": dict(sql_stats), "sql_count": sum(value["count"] for value in sql_stats.values()),
      "sql_wall_seconds": sum(value["wall_seconds"] for value in sql_stats.values()), "network": network,
      "samples": len(samples), "sampler_stopped": not sampler.is_alive(), "invalid_evidence": invalid_evidence,
      "cas_objects_verified": verified_objects, "cas_root_outside_workspace": str(store_root), "owned_job_final": owned_job.usage()})
print(json.dumps({"outcome": outcome, "wall_seconds": execute_wall, "cpu_seconds": execute_cpu, "counts": counts, "parsed_counts": parsed_counts, "sql_count": sum(value["count"] for value in sql_stats.values())}), flush=True)
