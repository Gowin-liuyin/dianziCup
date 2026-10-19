"""Record bounded fix checks without saving resource environment or credentials."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
PYTHON = "D:/dianzi/backend/.venv/Scripts/python.exe"


def record(label: str, argv: list[str], cwd: Path, timeout: int = 240) -> int:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "backend/src")
    environment["PYTHONIOENCODING"] = "utf-8"
    sensitive = []
    for name in ("TEST_DATABASE_URL", "TEST_REDIS_URL"):
        value = environment.get(name, "")
        if value:
            sensitive.append(value)
            sensitive.append(unquote(urlsplit(value).password or ""))
    started = datetime.now().astimezone().isoformat()
    result = subprocess.run(
        argv,
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    raw = result.stdout + result.stderr
    leaked = any(value and value in raw for value in sensitive)
    for value in sensitive:
        if value:
            raw = raw.replace(value, "[redacted test credential]")
    log = RUN / (label + ".log")
    if log.exists() or (RUN / (label + ".json")).exists():
        raise RuntimeError("evidence label already recorded")
    log.write_text(raw, encoding="utf-8", newline="\n")
    receipt: dict[str, object] = {
        "argv": argv,
        "cwd": str(cwd),
        "started_at": started,
        "ended_at": datetime.now().astimezone().isoformat(),
        "exit_code": result.returncode,
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
        "exact_dsn_or_password_match": leaked,
    }
    junit = RUN / (label + ".xml")
    if junit.exists():
        content = junit.read_text(encoding="utf-8")
        junit_leaked = any(value and value in content for value in sensitive)
        for value in sensitive:
            if value:
                content = content.replace(value, "[redacted test credential]")
        if junit_leaked:
            junit.write_text(content, encoding="utf-8", newline="\n")
        receipt["junit_exact_dsn_or_password_match"] = junit_leaked
        cases = ElementTree.fromstring(content).findall(".//testcase")
        receipt["counts"] = {
            "tests": len(cases),
            "failures": sum(case.find("failure") is not None for case in cases),
            "errors": sum(case.find("error") is not None for case in cases),
            "skipped": sum(case.find("skipped") is not None for case in cases),
        }
        leaked |= junit_leaked
    (RUN / (label + ".json")).write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                "label": label,
                "exit_code": result.returncode,
                "counts": receipt.get("counts"),
            }
        )
    )
    return result.returncode or int(leaked)


if __name__ == "__main__":
    label, *arguments = sys.argv[1:]
    if arguments[0] == "--external":
        raise SystemExit(record(label, arguments[1:], ROOT))
    raise SystemExit(record(label, [PYTHON, *arguments], ROOT / "backend"))
