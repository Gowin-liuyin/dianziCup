"""Run the original API, single worker, beat and exact observer inside an owned Job."""

from common import DATABASE, OBSERVER, OBSERVER_SHA, PRODUCT_SHA, QUEUE, ROOT, RUN, RUN_ID, now, script_manifest, verify_authorization, write

verify_authorization()

import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from runtime_limits import CPU_SECONDS_TOTAL, OwnedJob


def process_identity(pid):
    command = "$p=Get-CimInstance Win32_Process -Filter 'ProcessId=" + str(pid) + "'; if (-not $p) { exit 1 }; [ordered]@{pid=$p.ProcessId;creation_time=$p.CreationDate.ToUniversalTime().ToString('o');parent_pid=$p.ParentProcessId;executable=$p.ExecutablePath;command=$p.CommandLine} | ConvertTo-Json -Compress"
    return json.loads(subprocess.check_output(["powershell.exe", "-NoProfile", "-Command", command], text=True))


def main():
    job = OwnedJob()
    engine = create_engine(os.environ["DATABASE_URL"], hide_parameters=True, connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"})
    with engine.connect() as connection:
        assert connection.scalar(text("select current_database()")) == DATABASE
        assert connection.scalar(text("select version_num from alembic_version")) == "0016_source_response_receipts"
    secrets = tuple(value for value in json.loads(os.environ.pop("DIANZI_LOG_SECRET_VALUES")) if value)
    commands = {
        "api": [sys.executable, "-B", "-m", "uvicorn", "ai_intel.api.app:app", "--host", "127.0.0.1", "--port", "28013", "--log-level", "warning", "--no-access-log"],
        "worker": [sys.executable, "-B", "-m", "celery", "-A", "runtime_entry:celery_app", "worker", "--pool=solo", "--concurrency=1", "--queues=" + QUEUE, "--hostname=" + QUEUE + "@%h", "--loglevel=WARNING", "--without-gossip", "--without-mingle"],
        "beat": [sys.executable, "-B", "-m", "celery", "-A", "runtime_entry:celery_app", "beat", "--schedule", os.environ["DIANZI_BEAT_SCHEDULE_PATH"], "--loglevel=WARNING"],
        "observer": [sys.executable, "-B", str(OBSERVER / "observe.py")],
    }
    processes = {}
    threads = []
    log_limit = threading.Event()

    def drain(name, process):
        count = 0
        with (RUN / (name + ".log")).open("xb") as output:
            while chunk := process.stdout.readline(65536):
                for secret in sorted(secrets, key=len, reverse=True):
                    chunk = chunk.replace(secret.encode(), b"[REDACTED]")
                if count + len(chunk) > 8 * 1024**2:
                    log_limit.set()
                    break
                count += len(chunk)
                output.write(chunk)
                output.flush()

    clock = ZoneInfo("Asia/Shanghai")
    started = datetime.now(clock)
    hard_deadline = min(started + timedelta(seconds=21600), datetime.fromisoformat("2026-10-17T21:49:15+08:00"))
    observer_run = OBSERVER / ("live_" + RUN_ID)
    gate = {"root_live_authorized": True, "product_sha": PRODUCT_SHA, "observer_sha": OBSERVER_SHA, "product_root": str(ROOT), "run_id": RUN_ID, "segment_id": "segment_1", "started_at": started.isoformat(timespec="seconds"), "supervisor_limits_verified": True, "source_scope": ["nvd_ollama", "vllm_vendor", "osv_ollama", "avid_community", "ollama_releases", "trailofbits_blog", "arxiv_security", "nist_ai_rmf", "cac_generative_ai"], "maximum_seconds": 21600, "postgres_port": 25432, "redis_port": 26379, "opensearch_port": 29200}
    assert not (OBSERVER / "root_live_gate.json").exists()
    (OBSERVER / "root_live_gate.json").write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    write("root_live_gate_copy.json", gate)
    write("bootstrap_manifest.json", {"frozen_at": now(), "scripts": script_manifest(), "product_sha": PRODUCT_SHA, "observer_sha": OBSERVER_SHA, "observer_scripts_original_bytes": True, "owned_job_limits_verified": True, "observer_run": str(observer_run)})
    reason = "bounded_deadline"
    usage = job.usage()
    try:
        for name, command in commands.items():
            processes[name] = subprocess.Popen(command, cwd=ROOT / "backend", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=0x08000000)
            thread = threading.Thread(target=drain, args=(name, processes[name]), daemon=True)
            thread.start()
            threads.append(thread)
        write("runtime_start.json", {"started_at": started.isoformat(timespec="seconds"), "hard_deadline": hard_deadline.isoformat(timespec="seconds"), "product_sha": PRODUCT_SHA, "observer_sha": OBSERVER_SHA, "supervisor": process_identity(os.getpid()), "children": {name: process_identity(process.pid) for name, process in processes.items()}, "api_port": 28013, "frontend": "not_started", "redis_database": 15, "queue": QUEUE, "maximum_seconds": 21600, "memory_per_process_bytes": 512 * 1024**2, "memory_total_bytes": 2 * 1024**3, "host_cpu_percent": 20, "cpu_seconds_budget": CPU_SECONDS_TOTAL, "source_jobs_cap": 500, "saved_http_receipts_cap": 1000, "log_per_component_cap": 8 * 1024**2, "observer_snapshot_cap": 1024**2, "observer_journal_cap": 16 * 1024**2, "source_polling_enabled": True, "scheduler": "original_default_beat_only", "model_requests_permitted": 0, "observer_run": str(observer_run), "formal_six_hour_pass": False})
        deadline = time.monotonic() + max(0, (hard_deadline - started).total_seconds())
        last = 0
        while time.monotonic() < deadline and datetime.now(clock) < hard_deadline:
            if (RUN / "stop.request").exists():
                reason = "owned_stop_request"
                break
            if log_limit.is_set() or any(process.poll() is not None for process in processes.values()):
                reason = "log_budget_or_child_exit"
                break
            if (RUN / "minio_end.json").exists():
                reason = "minio_segment_ended"
                break
            usage = job.usage()
            with engine.connect() as connection:
                connection.execute(text("SET TRANSACTION READ ONLY"))
                stats = dict(connection.execute(text("select (select count(*) from job_runs where job_type='collect_public_source_page') source_jobs,(select count(*) from fetch_attempts) saved_http_receipts,(select coalesce(sum(attempt_count),0) from job_runs where job_type='collect_public_source_page') source_attempts,(select min(started_at) from job_runs where status='running') running_since")).mappings().one())
            if stats["source_jobs"] >= 500 or stats["saved_http_receipts"] >= 1000 or usage["cpu_seconds"] >= CPU_SECONDS_TOTAL:
                reason = "source_http_or_cpu_budget"
                break
            if stats["running_since"] and datetime.now(stats["running_since"].tzinfo).timestamp() - stats["running_since"].timestamp() > 35:
                reason = "source_running_watchdog"
                break
            if time.monotonic() - last >= 60:
                write("runtime_heartbeat.json", {"observed_at": now(), "product_sha": PRODUCT_SHA, "observer_sha": OBSERVER_SHA, "children_alive": {name: process.poll() is None for name, process in processes.items()}, "source_stats": stats, "usage": usage, "formal_six_hour_pass": False})
                last = time.monotonic()
            time.sleep(1)
    except Exception as error:
        reason = "supervisor_error_" + type(error).__name__
    finally:
        for name in ("beat", "worker", "api"):
            if name in processes and processes[name].poll() is None:
                processes[name].terminate()
        observer_run.mkdir(exist_ok=True)
        (observer_run / "collector_stop.request").write_text(now() + "\n")
        for name, process in processes.items():
            try:
                process.wait(timeout=40 if name == "observer" else 10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        for thread in threads:
            thread.join(timeout=2)
        (RUN / "minio_stop.request").write_text(now() + "\n")
        engine.dispose()
        write("runtime_end.json", {"started_at": started.isoformat(timespec="seconds"), "ended_at": now(), "product_sha": PRODUCT_SHA, "observer_sha": OBSERVER_SHA, "reason": reason, "exit_codes": {name: process.returncode for name, process in processes.items()}, "last_usage": usage, "formal_six_hour_pass": False})


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        write("runtime_failure.json", {"observed_at": now(), "error_type": type(error).__name__, "details": "withheld"})
        raise SystemExit(1) from None
