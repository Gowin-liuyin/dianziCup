"""Rerun only the setup-blocked regression and independent review probes."""

import json
import os
import subprocess
import sys

from review_runner import BACKEND, PYTHON, RUN, now
from sqlalchemy.engine import make_url


def main():
    config = json.loads(
        subprocess.check_output(
            [
                "wsl",
                "-d",
                "Ubuntu-22.04",
                "-u",
                "root",
                "--exec",
                "cat",
                "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json",
            ]
        )
    )
    original_url = make_url(config["TEST_DATABASE_URL"])
    assert (
        original_url.host in {"127.0.0.1", "localhost"} and original_url.port == 25432
    )
    assert original_url.database.startswith("test_")
    receipt = json.loads((RUN / "database_receipt.json").read_text())
    database = receipt["database"]
    assert database.startswith("test_dianzi_r11_inventory_review1_")
    run_id = database.removeprefix("test_dianzi_")
    assert len(run_id) <= 48
    url = original_url.set(
        drivername="postgresql+psycopg", host="127.0.0.1", database=database, query={}
    )
    environment = {
        **os.environ,
        "TEST_DATABASE_URL": url.render_as_string(hide_password=False),
        "DIANZI_TEST_RUN_ID": run_id,
        "PYTHONPATH": str(BACKEND / "src"),
        "PYTHONIOENCODING": "utf-8",
    }
    checks = [
        (
            "related_regression_recheck",
            [
                "tests/unit/test_t04_domain_contracts.py",
                "tests/unit/test_t06_access_scope_boundaries.py",
                "tests/unit/test_r02_auth_state_inputs.py",
                "tests/security/test_r02_auth_state_boundaries.py",
                "tests/contract/test_t07_jobs_outbox.py",
            ],
        ),
        ("independent_probes", [str(RUN / "review_probes.py")]),
    ]
    receipt_path = RUN / "supplement_commands.json"
    if "--probes-recheck" in sys.argv:
        checks = [("independent_probes_postformat", [str(RUN / "review_probes.py")])]
        receipt_path = RUN / "probe_recheck_commands.json"
    receipts = []
    for label, paths in checks:
        command = [
            str(PYTHON),
            "-m",
            "pytest",
            *paths,
            "--no-cov",
            "-q",
            "--junitxml=" + str(RUN / (label + ".xml")),
        ]
        started = now()
        result = subprocess.run(
            command,
            cwd=BACKEND,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=180,
            check=False,
        )
        output = result.stdout + result.stderr
        for secret in [environment["TEST_DATABASE_URL"], original_url.password or ""]:
            if secret:
                output = output.replace(secret, "[redacted test connection]")
        (RUN / (label + ".log")).write_text(output, encoding="utf-8")
        receipts.append(
            {
                "label": label,
                "argv": command,
                "cwd": str(BACKEND),
                "started_at": started,
                "finished_at": now(),
                "exit_code": result.returncode,
                "run_id": run_id,
                "isolation": "same_new_owned_test_database",
            }
        )
        receipt_path.write_text(json.dumps(receipts, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    "label": label,
                    "exit_code": result.returncode,
                    "summary": output.splitlines()[-1] if output else "",
                }
            ),
            flush=True,
        )
    return int(any(row["exit_code"] for row in receipts))


if __name__ == "__main__":
    raise SystemExit(main())
