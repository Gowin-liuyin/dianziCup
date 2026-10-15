"""仅前向迁移既有隔离来源库，核验永久证据原样保留。"""

import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text

from ai_intel.infrastructure.database import run_migrations

root = Path("C:/Users/yinha/.codex/worktrees/r04-real-pipeline/dianzi")
run = Path(__file__).resolve().parent / "product_live_23c1878"
run.mkdir(exist_ok=False)
sha = "23c18784d71f1ed788072e6b3f2af70bac94fcb1"
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip() == sha
engine = create_engine(os.environ["DATABASE_URL"], connect_args={"connect_timeout": 5})
assert engine.url.database == "test_dianzi_r04_pipeline_20261015"
clock = ZoneInfo("Asia/Shanghai")
started = datetime.now(clock).isoformat(timespec="seconds")


def snapshot():
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == engine.url.database
        rows = connection.execute(text("SELECT evidence_id, quote_sha256 FROM evidence ORDER BY evidence_id")).all()
        return {"evidence_count": len(rows), "evidence_identity_sha256": hashlib.sha256(json.dumps([list(row) for row in rows]).encode()).hexdigest(), "migration": connection.scalar(text("SELECT version_num FROM alembic_version")), "event_count": connection.scalar(text("SELECT count(*) FROM events"))}


try:
    before = snapshot()
    assert before["migration"] == "0013_revision_source_metadata"
    run_migrations(os.environ["DATABASE_URL"])
    after = snapshot()
    assert after["migration"] == "0014_grounded_answer_vectors"
    assert all(after[key] == before[key] for key in ("evidence_count", "evidence_identity_sha256", "event_count"))
    (run / "migration.json").write_text(json.dumps({"started_at": started, "ended_at": datetime.now(clock).isoformat(timespec="seconds"), "code_sha": sha, "database": engine.url.database, "before": before, "after": after, "exit_code": 0, "downgrade": "not_run"}, indent=2), encoding="utf-8")
    print("isolated source database migrated forward; permanent evidence unchanged")
finally:
    engine.dispose()
