"""Bounded own PG review: exact native identity, shared parent sampler, no other resources."""

import ctypes
from ctypes import wintypes
import hashlib
import json
import os
import subprocess
import threading
import time
import traceback
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import site
site.addsitedir("D:/dianzi/backend/.venv/Lib/site-packages")

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

import batch13_process_metadata as metadata
from pg_review_environment import BASELINE, PYTHON, QUALIFIED, ROOT, RUN, environment, now
import core_runtime_limits as limits
from parent_lock_observation import publish_lock_snapshot

SOURCE_OIDS = (10451302, 10434264)
MAXIMUM_SECONDS = 58
LABEL = sys.argv[1]



def main():
    if (RUN / (LABEL + ".command.json")).exists():
        raise RuntimeError("refusing_evidence_overwrite")
    started, monotonic_start = now(), time.monotonic()
    if (Path(sys.executable).resolve() != Path(PYTHON).resolve()
            or sys.prefix != sys.base_prefix or sys.version_info[:2] != (3, 12)):
        raise RuntimeError("approved_base_python_312_required")
    if os.environ.pop("DIANZI_REVIEW_RESOURCE_AUTHORIZED", "") != "r16-history-review1":
        raise RuntimeError("parent_resource_authorization_missing")
    allowed = json.loads(os.environ.pop("R18_REVIEW_BATCH_ALLOWLIST"))
    if not isinstance(allowed, list) or LABEL not in allowed:
        raise RuntimeError("batch_not_in_parent_allowlist")
    authorized_until = datetime.fromisoformat(os.environ.pop("R18_REVIEW_AUTHORIZED_UNTIL_UTC"))
    if authorized_until.tzinfo is None or datetime.now(authorized_until.tzinfo) >= authorized_until:
        raise RuntimeError("parent_resource_authorization_expired")
    remaining_auth = (authorized_until - datetime.now(authorized_until.tzinfo)).total_seconds()
    if authorized_until.utcoffset() != timedelta(0) or not 0 < remaining_auth <= 600:
        raise RuntimeError("authorization_must_be_UTC_and_at_most_ten_minutes")
    groups = json.loads((RUN / "pg_batch_plan.json").read_bytes())["groups"]
    group = next(item for item in groups if item["label"] == LABEL)
    nodes = group["nodes"]
    if not nodes or len(nodes) != group["expected_cases"]:
        raise RuntimeError("invalid_frozen_case_plan")
    admission = json.loads((RUN / "pg_controller_admission.json").read_bytes())
    for name, expected in admission["entry_raw_sha256"].items():
        if hashlib.sha256((RUN / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError("fixed_controller_input_hash_changed")
    for name, expected in admission["source_worktree_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError("fixed_source_hash_changed")
    limits.MEMORY_PER_PROCESS = 512 * 1024**2
    limits.MEMORY_TOTAL = 1024**3
    limits.CPU_RATE = 20000 // os.cpu_count()
    job = limits.OwnedJob()
    native_limits = job.query(9, limits.ExtendedLimits)
    native_limits.basic.flags |= 0x8
    native_limits.basic.active_limit = 9
    if not job.kernel.SetInformationJobObject(job.handle, 9, ctypes.byref(native_limits), ctypes.sizeof(native_limits)):
        raise RuntimeError("native_nine_process_limit_unavailable")
    native_limits = job.query(9, limits.ExtendedLimits)
    assert native_limits.basic.active_limit == 9
    native_cpu = job.query(15, limits.CpuRate)
    nonce = uuid4().hex[:12]
    run_id = "r16_change_history_http_" + nonce
    database = "test_dianzi_" + run_id
    parent = make_url(os.environ.pop("R18_REVIEW_PARENT_DATABASE_URL"))
    assert (parent.host, parent.port, parent.database, parent.username) == (
        "127.0.0.1", 25432, "test_dianzi_r01_20261014", "test_dianzi_r01")
    parent = parent.set(drivername="postgresql+psycopg")
    parent_dsn = parent.set(drivername="postgresql").render_as_string(hide_password=False)
    schema = "test_r16_review1_" + nonce
    target_url = parent.set(database=database).update_query_dict({
        "connect_timeout": "3",
        "options": "-c search_path=" + schema + ",public -c statement_timeout=8000 -c lock_timeout=5000",
    })
    marker = {
        "project": "dianzi", "kind": "isolated_integration_review", "run_id": run_id,
        "owner": "r16-history-review1:" + nonce, "product_sha": QUALIFIED,
        "maximum_seconds": MAXIMUM_SECONDS, "queue": "not_used", "redis_prefix": "not_used",
        "created_at": now(),
    }
    raw_marker = json.dumps(marker, separators=(",", ":"))
    marker_sha = hashlib.sha256(raw_marker.encode()).hexdigest()
    phase_file = RUN / (LABEL + ".phase.json")
    samples, sample_errors = [], []
    snapshot_file = RUN / (LABEL + ".parent-lock-snapshot.json")
    snapshot_reads = RUN / (LABEL + ".parent-lock-reads.jsonl")
    sampler_ready, resource_violation = threading.Event(), threading.Event()
    phase, stop = {"value": "preflight"}, threading.Event()
    created_oid, child, sampler_thread = None, None, None
    control, chain = metadata.control_root(metadata.current_identity())
    preexisting = metadata.descendants(control)
    peak, seen, residual, exit_code, error = {}, {}, [], None, None
    record = {"started_at": started, "candidate_sha": QUALIFIED, "baseline_sha": BASELINE,
              "maximum_seconds": MAXIMUM_SECONDS, "business_target_soft_cap": 2,
              "parent_sampler_cap": 1, "physical_target_plus_sampler_cap": 3,
              "owned_process_cap": 10, "created_database_allowlist": [database],
              "native_marker": marker, "source_databases_mutated": False,
              "paid_model_source_browser_requests": 0, "control_chain": chain}
    record["job_native_verified_before_spawn"] = {
        "process_memory_bytes": native_limits.process_memory,
        "job_memory_bytes": native_limits.job_memory,
        "cpu_rate": native_cpu.rate,
    }

    def terminate_children():
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = wintypes.HANDLE
        for pid, item in reversed(list(metadata.descendants(control).items())):
            if pid in preexisting:
                continue
            try:
                if metadata.identity(pid) != {"pid": pid, "birth_utc": item["birth_utc"]}:
                    continue
            except OSError:
                continue
            handle = kernel.OpenProcess(1, False, pid)
            if handle:
                kernel.TerminateProcess(wintypes.HANDLE(handle), 124)
                kernel.CloseHandle(wintypes.HANDLE(handle))

    def sample():
        try:
            with psycopg.connect(parent_dsn, connect_timeout=3, autocommit=True,
                                 options="-c statement_timeout=2000 -c lock_timeout=1000",
                                 application_name="r16_history_parent_sampler") as connection:
                sampler_pid = connection.info.backend_pid
                while not stop.is_set():
                    rows = connection.execute(
                        "SELECT pid,datname,usename,application_name,backend_start::text,state,wait_event_type,pg_blocking_pids(pid) "
                        "FROM pg_stat_activity WHERE backend_type='client backend' ORDER BY pid"
                    ).fetchall()
                    target = [row for row in rows if row[1] == database]
                    test_phase = phase["value"]
                    if phase_file.exists():
                        try:
                            test_phase = json.loads(phase_file.read_bytes())
                        except (OSError, ValueError):
                            pass
                    samples.append({"at": now(), "phase": test_phase, "sampler_pid": sampler_pid,
                                    "sampler_database": parent.database,
                                    "target_pids": [row[0] for row in target],
                                    "target_count": len(target), "target_plus_sampler": len(target) + 1,
                                    "all_client_count": len(rows), "all_client_rows": rows})
                    publish_lock_snapshot(snapshot_file, run_id=run_id, database=database,
                        marker_sha256=marker_sha, sampler_pid=sampler_pid, rows=rows)
                    sampler_ready.set()
                    if len(target) > 2:
                        resource_violation.set()
                    stop.wait(0.02)
        except Exception as caught:
            sample_errors.append(type(caught).__name__)

    try:
        with psycopg.connect(parent_dsn, connect_timeout=3, autocommit=True,
            options="-c statement_timeout=2000 -c lock_timeout=1000") as admin:
            identity = admin.execute(
                "SELECT current_database(),current_user,(SELECT rolsuper FROM pg_roles WHERE rolname=current_user),"
                "(SELECT rolconnlimit FROM pg_roles WHERE rolname=current_user),"
                "(SELECT setting FROM pg_settings WHERE name='max_connections')"
            ).fetchone()
            assert identity[:2] == ("test_dianzi_r01_20261014", "test_dianzi_r01")
            server_version = int(admin.execute("SHOW server_version_num").fetchone()[0])
            assert 160000 <= server_version < 170000
            record["parent_identity"] = {"server_version_num": server_version, "database": identity[0], "role": identity[1],
                "superuser": identity[2], "role_connection_limit": identity[3],
                "server_max_connections": int(identity[4]), "profile_two_is_soft": True,
                "backend_pid": admin.info.backend_pid}
            role_identity = admin.execute(
                "SELECT oid,shobj_description(oid,'pg_authid') FROM pg_roles WHERE rolname=current_user"
            ).fetchone()
            record["parent_role_identity"] = {"oid": role_identity[0], "comment": role_identity[1]}
            catalog = admin.execute(
                "SELECT datname,oid,pg_get_userbyid(datdba),shobj_description(oid,'pg_database') "
                "FROM pg_database ORDER BY oid"
            ).fetchall()
            record["catalog_before"] = [{"database": row[0], "oid": row[1], "owner": row[2],
                "comment_sha256": hashlib.sha256(row[3].encode()).hexdigest() if row[3] else None}
                for row in catalog]
            source_before = {row[1]: row for row in catalog if row[1] in SOURCE_OIDS}
            assert set(source_before) == set(SOURCE_OIDS)
            assert not any(row[0] == database for row in catalog)
            admin.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(
                sql.Identifier(database), sql.Identifier(parent.username)))
            admin.execute(sql.SQL("COMMENT ON DATABASE {} IS {}").format(
                sql.Identifier(database), sql.Literal(raw_marker)))
            native = admin.execute(
                "SELECT oid,pg_get_userbyid(datdba),shobj_description(oid,'pg_database') "
                "FROM pg_database WHERE datname=%s", (database,)).fetchone()
            created_oid = native[0]
            assert native[1:] == (parent.username, raw_marker)
            assert len(json.loads(native[2])) == 9 and nonce in json.loads(native[2])["owner"]
            record["created_native_identity"] = {"database": database, "oid": created_oid,
                "owner": native[1], "comment": native[2], "comment_sha256": marker_sha,
                "comment_exact_nine_fields": True, "nonce": nonce}
        sampler_thread = threading.Thread(target=sample)
        sampler_thread.start()
        if not sampler_ready.wait(3):
            raise RuntimeError("parent_sampler_not_ready")
        child_environment = environment()
        child_environment.update(TEST_DATABASE_URL=parent.set(database=database).render_as_string(hide_password=False),
            R18_REVIEW_MIGRATION_DATABASE_URL=target_url.render_as_string(hide_password=False),
            DIANZI_TEST_RUN_ID=run_id, R18_REVIEW_PHASE_FILE=str(phase_file),
            R18_PARENT_LOCK_SNAPSHOT=str(snapshot_file), R18_REVIEW_DATABASE=database,
            R18_REVIEW_MARKER_SHA256=marker_sha, R18_PARENT_LOCK_READ_RECEIPT=str(snapshot_reads))
        identity_file = RUN / (LABEL + ".identity.json")
        child_environment["R18_REVIEW_IDENTITY_FILE"] = str(identity_file)
        child_environment["PYTHONPATH"] += os.pathsep + str(RUN)
        with psycopg.connect(target_url.set(drivername="postgresql").render_as_string(hide_password=False),
                             connect_timeout=3, autocommit=True,
                             options="-c statement_timeout=2000 -c lock_timeout=1000") as extension:
            extension.execute("CREATE EXTENSION vector")
            extension.execute(sql.SQL("CREATE SCHEMA {} AUTHORIZATION {}").format(
                sql.Identifier(schema), sql.Identifier(parent.username)))
            schema_comment = "owned_schema:" + raw_marker
            extension.execute(sql.SQL("COMMENT ON SCHEMA {} IS {}").format(
                sql.Identifier(schema), sql.Literal(schema_comment)))
            schema_oid = extension.execute("SELECT oid FROM pg_namespace WHERE nspname=%s", (schema,)).fetchone()[0]
            extension.execute(sql.SQL('ALTER DATABASE {} SET search_path TO {}, public').format(sql.Identifier(database), sql.Identifier(schema)))
            identity_file.write_text(json.dumps({
                "run_id": run_id, "database": database, "database_oid": created_oid,
                "database_comment": raw_marker, "schema": schema, "schema_oid": schema_oid,
                "schema_comment": schema_comment,
                "role": parent.username, "role_oid": role_identity[0], "role_comment": role_identity[1],
                "source_sha": QUALIFIED,
            }, indent=2) + "\n", encoding="utf-8")
            record["owned_schema_identity"] = {"name": schema, "oid": schema_oid, "database_oid": created_oid}
        fixture_plugins = ["-p", "repository_fixture_plugin"] if group.get("requires_repository_fixture_plugin") else []
        command = [PYTHON, str(RUN / "worker_entry.py"), "pytest", "-p", "pg_phase_plugin",
                   "-p", "task_pg_identity", *fixture_plugins,
                   "-p", "reports.runs.r16_r17_change_history_review1_fix1_20261017.pg_collect_fixture_guard",
                   *nodes, "-q", "--no-cov", "--tb=short",
                   "--junitxml=" + str(RUN / (LABEL + ".xml"))]
        record["command"], record["cwd"] = command, str(ROOT / "backend")
        record["child_commands"] = []
        for child_phase, child_command in (
            ("migration", [PYTHON, str(RUN / "worker_entry.py"), "task_migration_entry"]),
            ("pytest", command),
        ):
            phase["value"] = child_phase
            suffix = ".migration" if child_phase == "migration" else ""
            with (RUN / (LABEL + suffix + ".stdout.log")).open("wb") as out, (RUN / (LABEL + suffix + ".stderr.log")).open("wb") as err:
                child = subprocess.Popen(child_command, cwd=ROOT / "backend", env=child_environment, stdout=out, stderr=err)
                child_start = now()
                while child.poll() is None:
                    tree = metadata.descendants(control)
                    seen.update(tree)
                    if len(tree) > len(peak):
                        peak = tree
                    if (len(tree) > 10 or resource_violation.is_set() or sample_errors
                            or datetime.now(authorized_until.tzinfo) >= authorized_until
                            or time.monotonic() - monotonic_start >= MAXIMUM_SECONDS - 10):
                        terminate_children()
                        error = "owned_process_resource_or_deadline_limit"
                        break
                    time.sleep(0.02)
                child.wait(timeout=5)
                exit_code = child.returncode
            record["child_commands"].append({"phase": child_phase, "argv": child_command,
                "started_at": child_start, "ended_at": now(), "exit_code": exit_code,
                "real_exit_observed_before_next_child": child.poll() is not None})
            if exit_code or error:
                error = error or child_phase + "_child_failed"
                break
        phase["value"] = "cleanup"
    except Exception as caught:
        error = type(caught).__name__
        record["exception_locations"] = [
            {"file": frame.filename, "line": frame.lineno, "function": frame.name}
            for frame in traceback.extract_tb(caught.__traceback__)]
    finally:
        if child is not None and child.poll() is None:
            terminate_children()
            child.wait(timeout=3)
        stop.set()
        if sampler_thread is not None:
            sampler_thread.join(timeout=5)
            if sampler_thread.is_alive():
                error = "parent_sampler_not_released"
        if created_oid is not None:
            with psycopg.connect(parent_dsn, connect_timeout=3, autocommit=True,
                options="-c statement_timeout=2000 -c lock_timeout=1000") as admin:
                native = admin.execute(
                    "SELECT oid,pg_get_userbyid(datdba),shobj_description(oid,'pg_database'),"
                    "(SELECT count(*) FROM pg_stat_activity WHERE datname=d.datname) "
                    "FROM pg_database d WHERE datname=%s", (database,)).fetchone()
                assert native == (created_oid, parent.username, raw_marker, 0)
                assert hashlib.sha256(native[2].encode()).hexdigest() == marker_sha
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))
                assert admin.execute("SELECT oid FROM pg_database WHERE datname=%s", (database,)).fetchone() is None
                source_after = {row[1]: row for row in admin.execute(
                    "SELECT datname,oid,pg_get_userbyid(datdba),shobj_description(oid,'pg_database') "
                    "FROM pg_database WHERE oid IN (%s,%s)", SOURCE_OIDS).fetchall()}
                assert source_after == source_before
                sampler_pids = sorted({item["sampler_pid"] for item in samples})
                if sampler_pids:
                    assert admin.execute(
                        "SELECT count(*) FROM pg_stat_activity WHERE pid = ANY(%s)", (sampler_pids,)
                    ).fetchone()[0] == 0
                record["cleanup"] = {"native_identity_verified_before_drop": True, "own_database_remaining": 0,
                    "target_connections": 0, "sampler_connections": 0, "source_identities_unchanged": True,
                    "cleanup_backend_pid": admin.info.backend_pid}
        active = metadata.descendants(control)
        residual = [item for pid, item in active.items() if pid in seen and pid not in preexisting]
        (RUN / (LABEL + ".samples.json")).write_text(json.dumps(samples, indent=2) + "\n", encoding="utf-8")
        record.update(ended_at=now(), elapsed_seconds=time.monotonic()-monotonic_start,
            exit_code=exit_code, error=error, sample_errors=sample_errors,
            windows_peak_count=len(peak), windows_peak_chain=list(peak.values()), remaining_owned_processes=residual,
            max_target_connections=max((item["target_count"] for item in samples), default=0),
            max_target_plus_parent_sampler=max((item["target_plus_sampler"] for item in samples), default=0),
            backend_pids=sorted({pid for item in samples for pid in item["target_pids"]}),
            sampler_pids=sorted({item["sampler_pid"] for item in samples}))
        actual_memory = job.query(9, limits.ExtendedLimits)
        actual_cpu = job.query(15, limits.CpuRate)
        record["job_limits"] = {
            "scope": "supervisor and descendants; outer tool ancestors counted separately",
            "process_memory_bytes": actual_memory.process_memory,
            "job_memory_bytes": actual_memory.job_memory,
            "native_active_process_limit": actual_memory.basic.active_limit,
            "cpu_rate": actual_cpu.rate,
            "host_cpu_count": os.cpu_count(),
            "effective_cpu_cores": actual_cpu.rate * os.cpu_count() / 10000,
            "usage": job.usage(),
            "limiter_raw_sha256": hashlib.sha256((RUN / "core_runtime_limits.py").read_bytes()).hexdigest(),
        }
        xml = RUN / (LABEL + ".xml")
        if xml.exists():
            cases = list(ET.parse(xml).getroot().iter("testcase"))
            record["counts"] = {"executed": len(cases),
                "distinct": len({(case.get('classname'),case.get('name')) for case in cases}),
                "passed": sum(not any(case.find(s) is not None for s in ('failure','error','skipped')) for case in cases),
                **{s:sum(case.find(s) is not None for case in cases) for s in ('failure','error','skipped')}}
        record["entry_raw_sha256"] = admission["entry_raw_sha256"]
        record["source_worktree_sha256"] = admission["source_worktree_sha256"]
        expected_cases = group["expected_cases"]
        counts = record.get("counts", {})
        if (counts.get("executed") != expected_cases or counts.get("distinct") != expected_cases
                or counts.get("passed") != expected_cases):
            error = record["error"] = error or "expected_cases_not_all_passed"
        record["expected_cases"] = expected_cases
        record["original_test_assertions_changed"] = "none; original history12 and independent fixture-mode1 unchanged; Root0031 exact dependency only"
        record["parent_bridge_approved"] = True
        record["controller_deadline_seconds"] = 58
        record["child_cutoff_seconds"] = 48
        secret_hits = []
        secrets = [parent_dsn, target_url.render_as_string(hide_password=False), parent.password]
        for artifact in RUN.glob(LABEL + ".*"):
            if artifact.is_file() and artifact.suffix not in {".py", ".zip"}:
                raw = artifact.read_bytes()
                if any(secret and secret.encode() in raw for secret in secrets):
                    secret_hits.append(artifact.name)
        record["secret_scan"] = {"passed": not secret_hits, "artifact_count": len(list(RUN.glob(LABEL + ".*")))}
        if secret_hits:
            error = record["error"] = "secret_artifact_scan_failed"
        (RUN / (LABEL + ".command.json")).write_text(json.dumps(record, indent=2)+"\n",encoding="utf-8")
        print(json.dumps({key:record.get(key) for key in ("exit_code","error","counts","elapsed_seconds", "max_target_connections","max_target_plus_parent_sampler","cleanup")}))
    return int(bool(exit_code or error or sample_errors or residual or record["max_target_connections"] > 2
                    or record["max_target_plus_parent_sampler"] > 3 or record["elapsed_seconds"] > MAXIMUM_SECONDS))


if __name__ == "__main__":
    raise SystemExit(main())
