"""Time exact cold entry imports with secret reads, connections and service actions denied."""

from __future__ import annotations

import importlib
import json
import os
import shlex
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
CORE = Path("D:/dianzi-runtime-cache/r06-f3-core-20261017")
ZONE = timezone(timedelta(hours=8))
ROLE = sys.argv[1]
EVENTS: list[dict[str, object]] = []
START = time.monotonic()
PHASE = "entry"
DENIED_OPERATIONS: dict[str, int] = {}
DENIED_FRAMES: list[dict[str, object]] = []
ENTRY_PATH = str(CORE / "deploy_runtime_entry.py").replace("\\", "/").casefold()


class UnsupportedOfflineOperation(RuntimeError):
    """The exact live path requested an operation excluded from this offline probe."""


def append_phase(phase: str) -> None:
    global PHASE
    PHASE = phase
    EVENTS.append({"phase": phase, "elapsed_seconds": time.monotonic() - START})


def audit(event: str, args: tuple[object, ...]) -> None:
    if event in {"socket.connect", "socket.connect_ex", "socket.bind", "socket.getaddrinfo"}:
        DENIED_OPERATIONS[event] = DENIED_OPERATIONS.get(event, 0) + 1
        frame = sys._getframe(1)
        frames = []
        for _ in range(10):
            if frame is None:
                break
            frames.append({
                "file": Path(frame.f_code.co_filename).name,
                "line": frame.f_lineno, "function": frame.f_code.co_name,
            })
            frame = frame.f_back
        DENIED_FRAMES.append({"event": event, "frames": frames})
        raise UnsupportedOfflineOperation("connection_or_service_denied")
    if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0]))
        parts = {part.casefold() for part in path.parts}
        if (
            path.name.casefold().startswith(".env")
            or parts.intersection({"keys", "holdout", "secrets", "secret", "dpapi"})
            or path.suffix.casefold() in {".dpapi", ".key", ".pem", ".pfx", ".p12"}
        ):
            DENIED_OPERATIONS["secret_read"] = DENIED_OPERATIONS.get("secret_read", 0) + 1
            raise UnsupportedOfflineOperation("secret_material_read_denied")
    if event == "subprocess.Popen":
        command = args[1]
        if isinstance(command, str):
            command = [part.strip('"') for part in shlex.split(command, posix=False)]
        if not isinstance(command, (list, tuple)) or not command:
            raise UnsupportedOfflineOperation("process_denied")
        if Path(str(command[0])).name.casefold() not in {"git", "git.exe"}:
            raise UnsupportedOfflineOperation("process_denied")
        if len(command) < 2 or command[1] not in {"rev-parse", "status", "ls-files", "show"}:
            raise UnsupportedOfflineOperation("git_mutation_denied")


def trace_entry(frame, event, arg):
    if event != "line":
        return trace_entry
    phases = {
        21: "binding_begin", 23: "binding_complete",
        31: "infrastructure_import_begin", 36: "settings_load_begin",
        37: "settings_load_complete", 49: "engine_build_boundary",
        50: "database_connect_boundary", 53: "ready_watcher_boundary",
        58: "product_worker_runtime_boundary",
    }
    phase = phases.get(frame.f_lineno)
    if phase:
        append_phase(phase)
    if frame.f_lineno >= 49:
        DENIED_OPERATIONS["live_entry_io_boundary"] = 1
        raise UnsupportedOfflineOperation("live_entry_io_boundary_denied")
    return trace_entry


def trace(frame, event, arg):
    if (
        event == "call"
        and frame.f_code.co_name == "load_owned_application"
        and frame.f_code.co_filename.replace("\\", "/").casefold() == ENTRY_PATH
    ):
        return trace_entry
    return None


def main() -> None:
    started = datetime.now(ZONE).isoformat()
    sys.addaudithook(audit)
    sys.settrace(trace)
    result = "not_run"
    error_type = None
    source_error_identifier = None
    try:
        if ROLE in {"worker", "beat"}:
            os.environ["DIANZI_OWNED_PROCESS_ROLE"] = ROLE
            append_phase("celery_cli_import_begin")
            importlib.import_module("celery.bin.celery")
            append_phase("celery_cli_import_complete")
            append_phase("owned_entry_import_begin")
            importlib.import_module("deploy_runtime_entry")
            result = "unexpected_entry_return"
        elif ROLE == "api":
            append_phase("uvicorn_import_begin")
            importlib.import_module("uvicorn.main")
            append_phase("uvicorn_import_complete")
            append_phase("api_app_import_begin")
            importlib.import_module("ai_intel.api.app")
            append_phase("api_app_import_complete")
            result = "offline_import_complete"
        else:
            raise ValueError("unknown fixed role")
    except UnsupportedOfflineOperation as error:
        result = "unsupported_offline_operation"
        error_type = type(error).__name__
        source_error_identifier = str(error)
    except Exception as error:
        result = "import_failed"
        error_type = type(error).__name__
        if isinstance(error, RuntimeError) and str(error) in {
            "live source configuration differs from reviewed scope",
            "owned source process role required",
        }:
            result = "offline_configuration_refused"
            source_error_identifier = str(error)
        if isinstance(error, ModuleNotFoundError) and error.name and error.name.replace(".", "_").isidentifier():
            source_error_identifier = error.name
    finally:
        sys.settrace(None)
    if DENIED_OPERATIONS and result == "offline_import_complete":
        result = "unsupported_offline_operation_caught_by_dependency"
    record = {
        "started_at": started, "ended_at": datetime.now(ZONE).isoformat(),
        "role": ROLE, "interpreter": sys.executable, "actual_cwd": os.getcwd(),
        "elapsed_seconds": time.monotonic() - START, "result": result,
        "error_type": error_type, "source_error_identifier": source_error_identifier,
        "last_phase": PHASE, "events": EVENTS,
        "secret_material_loaded": False, "live_settings_loaded": False,
        "database_connections": 0, "ready_watcher_started": False,
        "source_started": False, "network_requests": 0,
        "denied_operations": DENIED_OPERATIONS, "denied_frames": DENIED_FRAMES,
        "scope": "offline fixture configuration; exact import code, no live readiness claim",
    }
    (RUN / (ROLE + "_cold_entry.json")).write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "role": ROLE, "result": result, "error_type": error_type,
        "last_phase": PHASE, "seconds": record["elapsed_seconds"],
    }))
    raise SystemExit(0 if result == "offline_import_complete" else 2)


if __name__ == "__main__":
    main()
