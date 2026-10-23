"""Verify the loaded fixture story and compare the two asset assessments. Prints no secrets."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, insert, select, text

ROOT = Path(r"D:\dianzi")
ENV_FILE = ROOT / "reports" / "runs" / "story_fixture_20261023" / "pg.env"
OUT = ROOT / "reports" / "runs" / "story_fixture_20261023" / "story-verify.txt"


def password() -> str:
    values = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        values[key] = value
    return values["POSTGRES_PASSWORD"]


def main() -> int:
    sys.path.insert(0, str(ROOT / "backend" / "src"))
    os.chdir(ROOT / "backend")
    secret = password()
    url = f"postgresql+psycopg://story:{secret}@127.0.0.1:25499/story_fixture"
    engine = create_engine(url, hide_parameters=True)
    lines: list[str] = []
    try:
        with engine.connect() as connection:
            rule = connection.execute(
                text(
                    "SELECT status, version FROM condition_rule_versions "
                    "WHERE rule_id = '70251daf-f441-55d1-91d7-f830a11d7b03'"
                )
            ).one()
            lines.append(f"rule_status={rule.status} version={rule.version}")
            rows = connection.execute(
                text(
                    "SELECT assets.display_name, asset_snapshots.snapshot_id, "
                    "asset_snapshots.canonical_payload "
                    "FROM assets JOIN asset_snapshots "
                    "ON assets.asset_id = asset_snapshots.asset_id "
                    "WHERE assets.display_name LIKE '主路径夹具资产 %' "
                    "ORDER BY assets.display_name"
                )
            ).all()
            analyst = connection.execute(
                text("SELECT user_id FROM users WHERE username = 'main-path-analyst'")
            ).scalar_one()
        for name, snapshot_id, payload in rows:
            components = payload.get("components", [])
            version = components[0]["version"] if components else "missing"
            lines.append(f"asset={name} version={version} snapshot={snapshot_id}")
        token = "verify-" + uuid4().hex
        now = datetime.now(UTC)
        from ai_intel.api.auth_state import auth_sessions
        from ai_intel.assessment.assessment_service import AssessmentService
        from ai_intel.infrastructure.content_store import ContentStore

        with engine.begin() as connection:
            connection.execute(
                insert(auth_sessions).values(
                    session_hash=hashlib.sha256(token.encode()).hexdigest(),
                    user_id=analyst,
                    csrf_token="verify-unused",
                    issued_at=now,
                    expires_at=now + timedelta(minutes=10),
                )
            )
        store = ContentStore(ROOT / "reports" / "runs" / "story_fixture_20261023" / "raw")
        service = AssessmentService(engine, token, store)
        for name, snapshot_id, payload in rows:
            asset_id = engine.connect().execute(
                text("SELECT asset_id FROM asset_snapshots WHERE snapshot_id = :id"),
                {"id": snapshot_id},
            ).scalar_one()
            receipt = service.commit(
                service.prepare(
                    asset_id,
                    snapshot_id,
                    "70251daf-f441-55d1-91d7-f830a11d7b03",
                    1,
                )
            )
            lines.append(
                f"assessment={name} status={receipt.status} "
                f"missing={','.join(receipt.missing_requirements) or 'none'} "
                f"conflicts={','.join(receipt.conflicts) or 'none'}"
            )
    finally:
        engine.dispose()
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"postgresql://story:{secret}@127.0.0.1:25499/story_fixture",
            "DATA_MODE": "fixture",
            "APP_ENV": "development",
            "ADMIN_USER_PASSWORD": secret,
            "RAW_CONTENT_DIRECTORY": str(ROOT / "reports" / "runs" / "story_fixture_20261023" / "raw"),
            "CONTENT_STORE_BACKEND": "local",
        }
    )
    rerun = subprocess.run(
        ["uv", "run", "python", str(ROOT / "scripts" / "load_main_path_story.py")],
        cwd=ROOT / "backend",
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    lines.append(f"rerun_exit={rerun.returncode}")
    lines.append("rerun_stdout=" + rerun.stdout.strip())
    lines.append("rerun_stderr=" + rerun.stderr.strip())
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if rerun.returncode == 0 else rerun.returncode


if __name__ == "__main__":
    sys.exit(main())
