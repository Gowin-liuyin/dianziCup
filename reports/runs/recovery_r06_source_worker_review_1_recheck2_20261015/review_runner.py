"""Run frozen-source review checks with private test connections and immutable logs."""

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
DATABASE = "test_dianzi_r06_catalog_worker_20261015"
SOURCE_FILES = (
    "backend/src/ai_intel/ingestion/catalog_pages.py",
    "backend/src/ai_intel/ingestion/source_catalog.py",
    "backend/src/ai_intel/infrastructure/models/json_output.py",
    "backend/src/ai_intel/ingestion/source_jobs.py",
    "backend/src/ai_intel/api/source_routes.py",
    "backend/src/ai_intel/ingestion/sources/osv.py",
    "backend/src/ai_intel/ingestion/sources/github_releases.py",
)


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def main():
    label, mode, *argv = sys.argv[1:]
    assert mode in {"pure", "pg", "command"}
    assert not (RUN / f"{label}.log").exists(), "review logs must not be overwritten"
    environment = dict(os.environ)
    for field in ("TEST_DATABASE_URL", "TEST_REDIS_URL", "DIANZI_TEST_RUN_ID"):
        environment.pop(field, None)
    environment["COVERAGE_FILE"] = str(RUN / f".coverage_{label}")
    secrets = []
    engine = None
    before = None

    def public_snapshot():
        with engine.connect() as connection:
            names = inspect(connection).get_table_names(schema="public")
            assert names == [], "dedicated test database public must stay empty"
            return {"table_names": names}

    if mode == "pg":
        connection_info = json.loads(subprocess.check_output([
            "wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "cat",
            "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json",
        ], text=True))
        original = make_url(connection_info["TEST_DATABASE_URL"])
        assert original.database.startswith("test_")
        target = original.set(database=DATABASE)
        connection_url = target.render_as_string(hide_password=False)
        secrets = [connection_info["TEST_DATABASE_URL"], connection_url, target.password or ""]
        secrets += [unquote(value) for value in secrets if value]
        environment.update(TEST_DATABASE_URL=connection_url,
                           DIANZI_TEST_RUN_ID="r06_catalog_worker_20261015")
        engine = create_engine(target, connect_args={"connect_timeout": 5})
        before = public_snapshot()
    started = now()
    result = subprocess.run(argv, cwd=ROOT / "backend", env=environment,
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", check=False)
    ended = now()
    output = result.stdout + result.stderr
    for value in secrets:
        if value:
            output = output.replace(value, "[redacted test connection]")
    log = RUN / f"{label}.log"
    log.write_text(output, encoding="utf-8", newline="")
    after = public_snapshot() if engine is not None else None
    metadata = {
        "label": label, "mode": mode, "argv": argv, "cwd": str(ROOT / "backend"),
        "started_at": started, "ended_at": ended, "exit_code": result.returncode,
        "checkout_sha": subprocess.check_output(["git", "rev-parse", "HEAD"],
                                                cwd=ROOT, text=True).strip(),
        "product_code_sha": "1456e22f8187643a9978e9fa44d57c945e73b5bc",
        "source_hashes": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                          for name in SOURCE_FILES},
        "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
        "public_before": before, "public_after": after,
        "public_unchanged": before == after,
    }
    for argument in argv:
        if argument.startswith("--junitxml="):
            xml = Path(argument.split("=", 1)[1])
            if xml.exists():
                for value in secrets:
                    assert not value or value not in xml.read_text(encoding="utf-8")
                suites = ElementTree.parse(xml).getroot().iter("testsuite")
                metadata["tests"] = [{key: suite.attrib.get(key) for key in
                                      ("tests", "failures", "errors", "skipped", "time")}
                                     for suite in suites]
    (RUN / f"{label}.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps({"label": label, "exit_code": result.returncode,
                      "public_unchanged": before == after, "tail": output[-3500:]},
                     ensure_ascii=False))
    if engine is not None:
        engine.dispose()
    assert before == after
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
