"""执行本包的固定检查并保留原始日志、真实时钟和工具退出码。"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
RUN_DIRECTORY = Path(__file__).resolve().parent
TIMEZONE = timezone(timedelta(hours=8), "Asia/Shanghai")


def main() -> None:
    backend_root = REPOSITORY_ROOT / "backend"
    targeted_paths = ["tests/security/test_r01_secret_classification.py",
                      "tests/security/test_t06_authentication_and_scope.py"]
    checks = [
        ("targeted_final_3", ["uv", "run", "--locked", "pytest", *targeted_paths, "-q",
                            "--cov-fail-under=0", "--junitxml=" + str(RUN_DIRECTORY / "targeted_final_3.junit.xml")]),
        ("security_final_3", ["uv", "run", "--locked", "pytest", "tests/security", "-q",
                            "--cov-fail-under=0", "--junitxml=" + str(RUN_DIRECTORY / "security_final_3.junit.xml")]),
        ("ruff_final_3", ["uv", "run", "--locked", "ruff", "check", ".", "../scripts/security_scan.py"]),
        ("format_final_3", ["uv", "run", "--locked", "ruff", "format", "--check", ".", "../scripts/security_scan.py"]),
        ("type_final_3", ["uv", "run", "--locked", "mypy", "--explicit-package-bases", "--follow-imports=silent",
                        "../scripts/security_scan.py", *targeted_paths]),
        ("source_type_final_3", ["uv", "run", "--locked", "mypy", "src"]),
    ]
    environment = os.environ.copy()
    environment["MYPYPATH"] = str(backend_root / "src") + os.pathsep + str(REPOSITORY_ROOT)
    for check_name, argv in checks:
        log_path = RUN_DIRECTORY / (check_name + ".log")
        started_at = datetime.now(TIMEZONE).isoformat()
        started_timer = time.perf_counter()
        with log_path.open("wb") as log_file:
            result = subprocess.run(argv, cwd=backend_root, env=environment,
                                    stdout=log_file, stderr=subprocess.STDOUT, check=False)
        ended_at = datetime.now(TIMEZONE).isoformat()
        record = {
            "command": argv, "cwd": str(backend_root), "started_at": started_at,
            "ended_at": ended_at, "wall_seconds": time.perf_counter() - started_timer,
            "exit_code": result.returncode, "log": log_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "log_sha256": hashlib.sha256(log_path.read_bytes()).hexdigest(),
            "input_commit": "fd4f1d42e1ad2e39ff7c80897fd50511c3faf299",
        }
        junit_path = RUN_DIRECTORY / (check_name + ".junit.xml")
        if junit_path.exists():
            root = ET.parse(junit_path).getroot()
            cases = root.findall(".//testcase")
            record["counts"] = {"tests": len(cases),
                                "failures": len(root.findall(".//testcase/failure")),
                                "errors": len(root.findall(".//testcase/error")),
                                "skipped": len(root.findall(".//testcase/skipped"))}
        (RUN_DIRECTORY / (check_name + ".json")).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"check": check_name, "exit_code": result.returncode,
                          "counts": record.get("counts")}))


if __name__ == "__main__":
    main()
