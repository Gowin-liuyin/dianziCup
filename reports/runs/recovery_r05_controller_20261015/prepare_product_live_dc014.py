"""核对修复版本沿用的已迁移隔离库及历史回答，不重新迁移或删数据。"""

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text

run = Path(__file__).resolve().parent / "product_live_dc014c9"
assert not (run / "migration.json").exists()
engine = create_engine(os.environ["DATABASE_URL"], connect_args={"connect_timeout": 5})
assert engine.url.database == "test_dianzi_r04_pipeline_20261015"
with engine.connect() as connection:
    assert connection.scalar(text("SELECT current_database()")) == engine.url.database
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0014_grounded_answer_vectors"
    counts = {table: connection.scalar(text("SELECT count(*) FROM " + table)) for table in ("events", "evidence", "grounded_answers", "retrieval_chunks")}
    assert connection.scalar(text("SELECT count(*) FROM grounded_answers WHERE response->>'kind'='pending'")) == 0
(run / "migration.json").write_text(json.dumps({"observed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "schema": "0014_grounded_answer_vectors", "action": "read-only verification; no migration/reset", "counts": counts, "pending_legacy_answers": 0}, indent=2), encoding="utf-8")
engine.dispose()
print("isolated schema0014 and prior history verified; no legacy pending answer")
