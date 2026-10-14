"""运行入口导入与队列配置；合成连接仅检查装配，不计broker/PG live。"""

import importlib
import os
import subprocess
import sys

import pytest


def test_worker_refuses_missing_dependencies_before_starting() -> None:
    environment = dict(os.environ)
    environment.pop("DATABASE_URL", None)
    environment.pop("REDIS_URL", None)
    result = subprocess.run(
        [sys.executable, "-c", "import ai_intel.workers.runtime"],
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "DATABASE_URL and REDIS_URL are required for workers" in result.stderr


def test_worker_configuration_reuses_single_queue_and_discards_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://test_user@127.0.0.1:25432/test_fixture"
    )
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:26379/0")
    runtime = importlib.import_module("ai_intel.workers.runtime")
    application = runtime.build_celery_application()
    assert application.backend is None or application.conf.result_backend is None
    assert application.conf.accept_content == ["json"]
    assert application.conf.task_ignore_result is True
    assert application.conf.task_store_errors_even_if_ignored is False
    assert application.conf.worker_concurrency == 1
    assert application.conf.worker_prefetch_multiplier == 1
    assert application.conf.task_default_queue == "ai_intel"
    assert application.conf.broker_connection_retry_on_startup is False
    assert application.conf.task_time_limit == 30
    assert application.conf.beat_scheduler == "ai_intel.workers.runtime:ObservedScheduler"
    assert application.conf.beat_schedule["observe-worker"]["options"]["expires"] == 20
    application.close()
