"""真实MinIO/PG隔离验证；凭据只在内存与子进程环境，原始JUnit置私有目录。"""

import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def read_private(path: str) -> dict[str, str]:
    result = subprocess.run(["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec",
                             "cat", path], check=True, capture_output=True, text=True, timeout=10)
    return json.loads(result.stdout)


def main() -> int:
    label = sys.argv[1]
    if re.fullmatch(r"[a-z0-9_]{1,60}", label) is None:
        raise ValueError("invalid evidence label")
    if any((RUN / f"{label}{suffix}").exists() for suffix in (".xml", ".log", ".command.json")):
        raise FileExistsError("evidence label already exists")
    postgres = read_private("/tmp/dianzi-r02_knowledge_20261015/connection.json")
    objects = read_private("/tmp/dianzi-minio-r02-20261015/private/connection.json")
    environment = dict(os.environ)
    environment.update(TEST_DATABASE_URL=postgres["TEST_DATABASE_URL"],
                       DIANZI_TEST_RUN_ID="r02_knowledge_20261015",
                       TEST_MINIO_ENDPOINT=objects["endpoint"], TEST_MINIO_BUCKET=objects["bucket"],
                       TEST_MINIO_ACCESS_KEY=objects["access_key"],
                       TEST_MINIO_SECRET_KEY=objects["secret_key"],
                       PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    sensitive = {postgres["TEST_DATABASE_URL"], objects["access_key"], objects["secret_key"],
                 unquote(urlsplit(postgres["TEST_DATABASE_URL"]).password or "")}
    sensitive.discard("")
    sensitive.update(part[index:index + 8] for part in list(sensitive)
                     for index in range(len(part) - 7))

    def redact(value: str) -> str:
        for secret in sorted(sensitive, key=len, reverse=True):
            value = value.replace(secret, "[REDACTED]")
        return value

    private_directory = Path(os.environ["USERPROFILE"]) / ".codex/secrets/dianzi"
    descriptor, filename = tempfile.mkstemp(prefix="r02-minio-junit-", suffix=".xml",
                                           dir=private_directory)
    os.close(descriptor)
    private_xml = Path(filename).resolve()
    if not private_xml.is_relative_to(private_directory.resolve()):
        raise ValueError("private artifact path outside designated secret directory")
    command = ["uv", "run", "--locked", "pytest", "tests/unit",
               "tests/integration/test_r02_minio_persistence.py",
               "tests/integration/test_r02_knowledge_revisions.py",
               "tests/integration/test_r02_relation_identity_regressions.py",
               f"--junitxml={private_xml}", "-q"]
    started = now()
    completed = subprocess.run(command, cwd=ROOT / "backend", env=environment,
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=240)
    sanitized = redact(completed.stdout + completed.stderr)
    (RUN / f"{label}.log").write_text(sanitized, encoding="utf-8")
    if private_xml.exists():
        (RUN / f"{label}.xml").write_text(redact(private_xml.read_text(encoding="utf-8")),
                                          encoding="utf-8")
        private_xml.unlink()
    command[-2] = "--junitxml=<private temporary file; sanitized copy retained>"
    receipt = {"started_at": started, "ended_at": now(), "exit_code": completed.returncode,
               "command": command, "cwd": str(ROOT / "backend"),
               "parent_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                                     text=True).strip(),
               "source_state": "uncommitted root-owned MinIO implementation on recorded parent",
               "database_scope": "r02_knowledge_20261015", "object_scope": objects["bucket"],
               "model_or_source_live": False, "known_secret_artifact_matches": 0}
    matches = sum(secret in sanitized for secret in sensitive)
    receipt["known_secret_artifact_matches"] = matches
    (RUN / f"{label}.command.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt))
    print(sanitized[-1800:])
    return completed.returncode if matches == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
