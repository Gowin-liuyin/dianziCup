"""Record bounded commands, timestamps and untouched raw failure evidence."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

from sqlalchemy.engine import make_url

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
PYTHON = "D:/dianzi/backend/.venv/Scripts/python.exe"


def credential_values() -> tuple[str, ...]:
    result = subprocess.run(
        [
            "C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/"
            "dependencies/native/powershell/pwsh.exe", "-NoProfile", "-Command",
            "$forwardProtected=Get-Content -LiteralPath "
            "'D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi' -Raw; "
            "$forwardClear=$forwardProtected | ConvertTo-SecureString | "
            "ConvertFrom-SecureString -AsPlainText; [Console]::Write($forwardClear)",
        ], capture_output=True, timeout=15, check=True,
    )
    original_text = json.loads(result.stdout)["TEST_DATABASE_URL"]
    original = make_url(original_text)
    assert original.host == "127.0.0.1" and original.port == 25432
    values = [original_text, original.password or ""]
    marker = RUN / "owned_database.json"
    if marker.exists():
        owned = json.loads(marker.read_text(encoding="utf-8"))["database"]
        assert owned.startswith("test_forward26_")
        values.append(original.set(database=owned).render_as_string(hide_password=False))
    return tuple(value for value in values if value)


def main() -> int:
    label, *arguments = sys.argv[1:]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "backend/src")
    environment["PYTHONIOENCODING"] = "utf-8"
    started = datetime.now().astimezone().isoformat()
    result = subprocess.run(
        arguments,
        cwd=ROOT / "backend",
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    raw = result.stdout + result.stderr
    scans: list[dict[str, object]] = []
    leaked = False
    if label.startswith("pg_"):
        credentials = credential_values()
        leaked = any(value in raw for value in credentials)
        for value in credentials:
            raw = raw.replace(value, "[redacted test credential]")
        for path in RUN.glob("*.xml"):
            content = path.read_text(encoding="utf-8")
            hit = any(value in content for value in credentials)
            scans.append({"file": path.name, "exact_dsn_or_password": hit})
            leaked |= hit
            if hit:
                for value in credentials:
                    content = content.replace(value, "[redacted test credential]")
                path.write_text(content, encoding="utf-8", newline="\n")
    (RUN / (label + ".log")).write_text(raw, encoding="utf-8", newline="\n")
    receipt: dict[str, object] = {
        "argv": arguments,
        "cwd": str(ROOT / "backend"),
        "started_at": started,
        "ended_at": datetime.now().astimezone().isoformat(),
        "exit_code": result.returncode,
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "credential_scan": {"exact_dsn_or_password": leaked, "junit": scans},
    }
    junit = RUN / (label + ".xml")
    if junit.exists():
        suites = ElementTree.parse(junit).getroot().findall("testsuite")
        receipt["counts"] = {
            key: sum(int(suite.get(key, "0")) for suite in suites)
            for key in ("tests", "failures", "errors", "skipped")
        }
    (RUN / (label + ".json")).write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(receipt))
    if result.returncode:
        print(raw[-9000:])
    return result.returncode if result.returncode else (1 if leaked else 0)


if __name__ == "__main__":
    raise SystemExit(main())
