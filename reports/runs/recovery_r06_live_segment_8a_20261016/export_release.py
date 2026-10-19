"""Export the root-authorized public response through verified MinIO into a new file."""

from common import now, verify_authorization, write

verify_authorization()

import hashlib
import json
import os
from pathlib import Path

from sqlalchemy import create_engine, text
from ai_intel.infrastructure.content_storage_factory import build_content_storage
from ai_intel.infrastructure.settings import load_application_settings

digest = "25e00623a07dcafe8d8d6b3535e400e078ef758e965742a37fe76d5186bb69f7"
target = Path("D:/dianzi-local-evidence/recovery_r06_live_segment_8a_20261016/release_raw.bin")
assert str(target.resolve()).replace("\\", "/") == "D:/dianzi-local-evidence/recovery_r06_live_segment_8a_20261016/release_raw.bin"
assert not target.exists()
assert not any(parent.is_symlink() for parent in target.parents)
store = build_content_storage(load_application_settings())
body = store.read_verified(digest)
assert len(body) == 616865 and hashlib.sha256(body).hexdigest() == digest
target.parent.mkdir(parents=True, exist_ok=True)
with target.open("xb") as output:
    output.write(body)
engine = create_engine(os.environ["DATABASE_URL"], hide_parameters=True, connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"})
with engine.connect() as connection:
    connection.execute(text("SET TRANSACTION READ ONLY"))
    receipts = [dict(row) for row in connection.execute(text("select source_kind,source_id,job_id,attempt_count,response_ordinal,stream_kind,window_end,observed_at,http_status,content_type,response_content_hash,response_size_bytes,parse_outcome,error_code from source_response_receipts where response_content_hash=:hash"), {"hash": digest}).mappings()]
    assert len(receipts) == 1
    row = connection.execute(text("select payload from job_payloads where job_id=:job"), {"job": receipts[0]["job_id"]}).one()
    payload = json.loads(bytes(row[0]))
    assert set(payload) <= {"source_kind", "window_end", "stream_kind", "remaining_pages"}
engine.dispose()
write("release_export_receipt.json", {"exported_at": now(), "absolute_path": str(target), "sha256": digest, "size_bytes": len(body), "store": "actual MinIO read_verified", "official_public_source": "https://api.github.com/repos/ollama/ollama/releases", "source_receipt": receipts[0], "minimal_source_job_payload": payload, "source_network_requests": 0, "raw_body_in_repository_or_log": False})
print(json.dumps({"path": str(target), "sha256": digest, "size_bytes": len(body), "read_verified": True}))
