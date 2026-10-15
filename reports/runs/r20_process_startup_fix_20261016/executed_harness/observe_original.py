"""Observe unmodified native hard-exit tests from the parent using process query handles only."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from observe_boundaries import cpu_snapshot, kernel

RUN = Path(__file__).resolve().parent
records: list[dict[str, object]] = []
original_popen = subprocess.Popen


class ObservedStream:
    def __init__(self, stream: object, record: dict[str, object], handles: list[int]) -> None:
        self.stream, self.record, self.handles = stream, record, handles

    def __getattr__(self, name: str) -> object:
        return getattr(self.stream, name)

    def readline(self, *args: object) -> bytes:
        line = self.stream.readline(*args)
        if line.startswith(b"TREE "):
            self.record["ready_perf_counter"] = time.perf_counter()
            self.record["pids"] = [int(value) for value in line.split()[1:]]
            for pid in self.record["pids"]:
                handle = kernel.OpenProcess(0x100000 | 0x1000, False, pid)
                if not handle:
                    raise RuntimeError("diagnostic process query failed")
                self.handles.append(handle)
            self.record["ready_cpu"] = [cpu_snapshot(handle) for handle in self.handles]
        return line


class ObservedPopen(original_popen):
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.diagnostic_record: dict[str, object] | None = None
        self.diagnostic_handles: list[int] = []
        super().__init__(*args, **kwargs)
        if (
            args
            and isinstance(args[0], list)
            and any("print('TREE'" in str(part) for part in args[0])
        ):
            self.diagnostic_record = {
                "started_at": datetime.datetime.now().astimezone().isoformat(),
                "launch_perf_counter": time.perf_counter(),
                "cov_environment": {
                    k: v for k, v in os.environ.items() if k.startswith("COV_CORE_")
                },
                "argv": args[0],
                "fixture": False,
            }
            records.append(self.diagnostic_record)
            assert self.stdout is not None
            self.stdout = ObservedStream(
                self.stdout, self.diagnostic_record, self.diagnostic_handles
            )

    def __exit__(self, *args: object) -> object:
        result = super().__exit__(*args)
        if self.diagnostic_record is not None:
            self.diagnostic_record.update(
                exited_at=datetime.datetime.now().astimezone().isoformat(),
                exit_perf_counter=time.perf_counter(),
                exit_code=self.returncode,
                final_cpu=[cpu_snapshot(handle) for handle in self.diagnostic_handles],
                tree_signaled=[
                    kernel.WaitForSingleObject(handle, 0) == 0 for handle in self.diagnostic_handles
                ],
            )
            for handle in self.diagnostic_handles:
                kernel.CloseHandle(handle)
        return result


class ObserverPlugin:
    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_call(self, item: object) -> object:
        subprocess.Popen = ObservedPopen
        try:
            yield
        finally:
            subprocess.Popen = original_popen


if __name__ == "__main__":
    name, *arguments = sys.argv[1:]
    coverage_file = Path.cwd() / ".coverage"
    prior = {"exists": coverage_file.exists()}
    if coverage_file.exists():
        prior.update(
            size=coverage_file.stat().st_size,
            sha256=hashlib.sha256(coverage_file.read_bytes()).hexdigest(),
        )
    exit_code = pytest.main(arguments, plugins=[ObserverPlugin()])
    (RUN / f"{name}.observations.json").write_text(
        json.dumps(
            {"records": records, "pytest_exit_code": exit_code, "coverage_data_before": prior},
            indent=2,
        ),
        encoding="utf-8",
    )
    raise SystemExit(exit_code)
