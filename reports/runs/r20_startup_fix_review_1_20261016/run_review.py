"""Keep independent command receipts without modifying product or original tests."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
PYTHON = "D:/dianzi/backend/.venv/Scripts/python.exe"
SHANGHAI = datetime.timezone(datetime.timedelta(hours=8))


def record(name: str, argv: list[str], *, cwd: Path | None = None, timeout: int = 60) -> int:
    started = datetime.datetime.now(SHANGHAI).isoformat(timespec="seconds")
    clock = time.monotonic()
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "COMSPEC", "PATHEXT", "USERPROFILE", "LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "WSLENV"}
    }
    environment.update(PYTHONPATH=str(ROOT / "backend/src"), PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    result = subprocess.run(argv, cwd=cwd or ROOT / "backend", env=environment, capture_output=True, timeout=timeout, check=False)
    (RUN / f"{name}.stdout.log").write_bytes(result.stdout)
    (RUN / f"{name}.stderr.log").write_bytes(result.stderr)
    receipt = {
        "name": name, "argv": argv, "cwd": str(cwd or ROOT / "backend"),
        "started_shanghai": started, "ended_shanghai": datetime.datetime.now(SHANGHAI).isoformat(timespec="seconds"),
        "exit_code": result.returncode, "wall_seconds": time.monotonic() - clock,
        "frozen_sha": "535c0a537bc24cb52c64511c72eeb4ea3ae5bc34", "code_sha": "41c61491b4429cc47dd970b201d9b2551cbb3a7f",
    }
    xml_path = RUN / f"{name}.xml"
    if xml_path.exists():
        suites = ET.parse(xml_path).getroot().findall("testsuite")
        receipt["junit_counts"] = {field: sum(int(suite.attrib.get(field, 0)) for suite in suites) for field in ("tests", "failures", "errors", "skipped")}
        receipt["actual_case_ids"] = [case.attrib["name"] for suite in suites for case in suite.findall("testcase")]
    receipt["stdout_sha256"] = hashlib.sha256(result.stdout).hexdigest()
    receipt["stderr_sha256"] = hashlib.sha256(result.stderr).hexdigest()
    (RUN / f"{name}.receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))
    return result.returncode


if __name__ == "__main__":
    name, *argv = sys.argv[1:]
    raise SystemExit(record(name, argv))
