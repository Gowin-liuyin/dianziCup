"""Serve the unchanged default application and stop its own pools through lifespan."""

import ctypes
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import uvicorn
from pydantic import SecretStr

from ai_intel.api.app import create_application
from ai_intel.infrastructure.settings import ApplicationSettings

RUN = Path(__file__).resolve().parent


if __name__ == "__main__":
    settings = ApplicationSettings(app_env="test", data_mode="fixture", database_url=SecretStr(os.environ["TEST_DATABASE_URL"]), allowed_origins=("http://127.0.0.1:26873",), raw_content_directory=str(RUN / "synthetic_raw"), dependency_timeout_seconds=3, redis_url=None, opensearch_url=None, generation_api_key=None, source_polling_enabled=False, enrichment_generation_enabled=False)
    application = create_application(settings=settings)
    server = uvicorn.Server(uvicorn.Config(application, host="127.0.0.1", port=28873, access_log=False, log_level="warning"))
    thread = threading.Thread(target=server.run, name="r17-owned-default-api")
    session_id = ctypes.c_ulong()
    ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session_id))
    thread.start()
    for _ in range(100):
        if server.started or not thread.is_alive():
            break
        time.sleep(0.1)
    boot = {"pid": os.getpid(), "parent_pid": os.getppid(), "session_id": session_id.value, "nonce": os.environ["R17_BOOT_NONCE"], "started_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "port": 28873, "default_factory": str(Path(create_application.__code__.co_filename).resolve()), "started": server.started}
    (RUN / "api_boot.json").write_text(json.dumps(boot, indent=2) + "\n", encoding="utf8")
    if not server.started:
        raise SystemExit(1)
    try:
        assert input().strip() == "stop"
    finally:
        server.should_exit = True
        thread.join(timeout=15)
        assert not thread.is_alive()
        (RUN / "api_shutdown.json").write_text(json.dumps({"pid": os.getpid(), "nonce": os.environ["R17_BOOT_NONCE"], "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "lifespan_completed": True}) + "\n", encoding="utf8")
