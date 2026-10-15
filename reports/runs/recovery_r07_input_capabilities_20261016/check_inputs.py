"""Run isolated bounded-input checks with actual command, times, exit and JUnit counts."""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
ZONE = ZoneInfo("Asia/Shanghai")


def now():
    return datetime.now(ZONE).isoformat()


def main():
    mode = sys.argv[1]
    run_stamp = datetime.now(ZONE).strftime("%H%M%S")
    environment = os.environ.copy()
    private = {}
    test_name = None
    if mode == "integration":
        private = json.loads(subprocess.check_output([
            "wsl.exe", "-u", "root", "--exec", "cat",
            "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json",
        ], stderr=subprocess.PIPE))
        original = make_url(private["TEST_DATABASE_URL"])
        assert original.username.startswith("test_") and original.database.startswith("test_dianzi_")
        run_id = "r07_inputs_" + datetime.now(ZONE).strftime("%m%d_%H%M%S") + "_" + uuid4().hex[:5]
        test_name = "test_dianzi_" + run_id
        admin = create_engine(original.set(database="postgres"), isolation_level="AUTOCOMMIT")
        with admin.connect() as connection:
            connection.execute(text('CREATE DATABASE "' + test_name + '"'))
        admin.dispose()
        environment["TEST_DATABASE_URL"] = original.set(database=test_name).render_as_string(hide_password=False)
        environment["DIANZI_TEST_RUN_ID"] = run_id
    paths = {
        "unit": ["tests/unit/test_r07_input_capabilities.py"],
        "contract": ["tests/contract/test_r07_input_selection_codec.py"],
        "security": ["tests/security/test_r07_input_capabilities_boundary.py"],
        "integration": ["tests/integration/test_r07_input_capabilities_pg.py"],
        "regression": ["tests/unit/test_r07_model_fields.py", "tests/unit/test_r07_single_model_dimension.py",
                       "tests/unit/test_r07_model_field_root_causes.py"],
        "fieldset": ["tests/unit/test_r07_enrichment_contracts.py", "tests/unit/test_r07_public_signals.py",
                     "tests/unit/test_r10_relation_polarity.py"],
    }
    commands = [[sys.executable, "-m", "pytest", "-q", *paths[mode], "--no-cov",
                 "--junitxml", str(RUN / (mode + "_" + datetime.now(ZONE).strftime("%H%M%S") + ".xml"))]] if mode != "static" else [
        [sys.executable, "-m", "ruff", "check", "src/ai_intel/enrichment/evidence_selection.py",
         "src/ai_intel/enrichment/taxonomy_inputs.py", "src/ai_intel/enrichment/model_fields.py",
         "tests/unit/test_r07_input_capabilities.py", "tests/contract/test_r07_input_selection_codec.py",
         "tests/security/test_r07_input_capabilities_boundary.py", "tests/integration/test_r07_input_capabilities_pg.py"],
        [sys.executable, "-m", "ruff", "format", "--check", "src/ai_intel/enrichment/evidence_selection.py",
         "src/ai_intel/enrichment/taxonomy_inputs.py", "src/ai_intel/enrichment/model_fields.py",
         "tests/unit/test_r07_input_capabilities.py", "tests/contract/test_r07_input_selection_codec.py",
         "tests/security/test_r07_input_capabilities_boundary.py", "tests/integration/test_r07_input_capabilities_pg.py"],
        [sys.executable, "-m", "mypy", "src/ai_intel/enrichment/evidence_selection.py",
         "src/ai_intel/enrichment/taxonomy_inputs.py", "src/ai_intel/enrichment/model_fields.py"],
        ["git", "diff", "--check"],
    ]
    records = []
    final_code = 0
    for index, command in enumerate(commands):
        started = now()
        result = subprocess.run(command, cwd=ROOT / "backend", env=environment, capture_output=True, text=True)
        output = result.stdout + result.stderr
        for secret in (private.get("TEST_DATABASE_URL"), private.get("postgres_password"), environment.get("TEST_DATABASE_URL")):
            if secret:
                output = output.replace(secret, "[redacted test connection]")
        record = {"mode": mode, "started_at": started, "completed_at": now(), "command": command,
                  "cwd": str(ROOT / "backend"), "exit_code": result.returncode,
                  "isolated_database": test_name}
        if mode != "static":
            report = Path(command[-1])
            cases = ElementTree.parse(report).findall(".//testcase")
            record.update(tests=len(cases), failed=sum(case.find("failure") is not None for case in cases),
                          errors=sum(case.find("error") is not None for case in cases),
                          skipped=sum(case.find("skipped") is not None for case in cases))
            report.with_suffix(".log").write_text(output, encoding="utf-8")
            report.with_suffix(".json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        else:
            (RUN / f"static_{run_stamp}_{index}.log").write_text(output, encoding="utf-8")
        records.append(record)
        final_code = final_code or result.returncode
        print(json.dumps({key: value for key, value in record.items() if key not in ("command", "cwd")}))
        print(output[-4000:])
    if mode == "static":
        (RUN / f"static_commands_{run_stamp}.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    return final_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("input_checks_failed:" + type(error).__name__)
        raise SystemExit(2) from None
