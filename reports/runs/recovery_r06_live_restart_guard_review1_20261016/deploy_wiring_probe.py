"""Explicit isolated fixture proves both bound task runs fence before the captured originals."""

import json
from pathlib import Path
import runpy
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

RUN = Path(__file__).resolve().parent
PREP = RUN.parent / "recovery_r06_live_restart_preparation_20261016"
sys.path.insert(0, str(PREP))
import authorization
import owned_stop_watcher
import task_fence
from celery.exceptions import WorkerShutdown


def main():
    calls = []
    database = ModuleType("ai_intel.infrastructure.database")
    database.build_engine = Mock()
    settings = ModuleType("ai_intel.infrastructure.settings")
    settings.load_application_settings = lambda: SimpleNamespace(
        source_polling_enabled=True, data_mode="live", content_store_backend="minio",
        generation_api_key=None,
    )
    runtime = ModuleType("ai_intel.workers.runtime")
    configuration = Mock()
    configuration.broker_transport_options = {}
    runtime.celery_app = SimpleNamespace(
        tasks={"ai_intel.jobs.execute": SimpleNamespace(run=None),
               "ai_intel.sources.poll_due": SimpleNamespace(run=None)}, conf=configuration)
    runtime.consume_job = lambda job_id: calls.append(("consume", job_id))
    runtime.poll_due_public_sources = lambda: calls.append(("poll",))
    environment = {"DIANZI_OWNED_PROCESS_ROLE": "worker"}
    with patch.object(authorization, "verify_live_authorization", return_value={}), \
         patch.object(owned_stop_watcher, "install_owned_stop_watcher"), \
         patch.dict("os.environ", environment), \
         patch.dict(sys.modules, {database.__name__: database, settings.__name__: settings, runtime.__name__: runtime}), \
         patch.object(task_fence, "read_stop_request", return_value=True):
        loaded = runpy.run_path(str(PREP / "deploy_runtime_entry.py"), run_name="review_fixture_deploy")
        results = []
        for task_name, arguments in (("ai_intel.jobs.execute", ("fixture-job",)), ("ai_intel.sources.poll_due", ())):
            try:
                loaded["celery_app"].tasks[task_name].run(*arguments)
            except WorkerShutdown as stopped:
                results.append({"task": task_name, "shutdown_code": stopped.code,
                                "original_call_count": len(calls), "pg_connect_count": database.build_engine.return_value.connect.call_count})
        assert len(results) == 2 and not calls
        assert database.build_engine.return_value.connect.call_count == 0
    result = {"fixture_mode": True, "gate_bypass_scope": "isolated in-process mocked imports only",
              "results": results, "source_http_count": 0, "model_provider_count": 0,
              "service_start_count": 0}
    output_name = sys.argv[1] if len(sys.argv) > 1 else "deploy_wiring_results.json"
    (RUN / output_name).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
