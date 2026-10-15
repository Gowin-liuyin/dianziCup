"""记录修复版本PG实际调用轨迹，与浏览器完整耗时分开留档。"""

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text

run = Path(__file__).resolve().parent / "product_live_dc014c9"
assert not (run / "pg_answer_trace.json").exists()
start = json.loads((run / "runtime_start.json").read_text(encoding="utf-8"))
engine = create_engine(os.environ["DATABASE_URL"], connect_args={"connect_timeout": 5})
assert engine.url.database == "test_dianzi_r04_pipeline_20261015"
with engine.connect() as connection:
    rows = [dict(row) for row in connection.execute(text("SELECT answer_id,response,model_trace,scope_epochs,created_at FROM grounded_answers WHERE created_at>=:since ORDER BY created_at"), {"since": datetime.fromisoformat(start["started_at"])}).mappings()]
    chunks = connection.scalar(text("SELECT count(*) FROM retrieval_chunks"))
record = {"observed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "code_sha": start["code_sha"], "rows": rows, "actual_supplier_attempts": sum(len(row["model_trace"].get("attempts", [])) for row in rows), "retrieval_chunk_count": chunks, "index_state": "20 same-model-space evidence chunks existed before this segment; query embedding/reranking and generation run again", "fee": "unknown", "quality_or_sla_evaluation": "not_run"}
encoded = json.dumps(record, ensure_ascii=False, indent=2, default=str)
secrets = json.loads(os.environ.pop("DIANZI_LOG_SECRET_VALUES"))
for secret in sorted({value for value in secrets if value} | {value[index:index + 8] for value in secrets if value for index in range(max(0, len(value) - 7))}, key=len, reverse=True):
    encoded = encoded.replace(secret, "[REDACTED]")
(run / "pg_answer_trace.json").write_text(encoded, encoding="utf-8")
engine.dispose()
print(json.dumps({"record_count": len(rows), "actual_supplier_attempts": record["actual_supplier_attempts"], "fee": "unknown"}))
