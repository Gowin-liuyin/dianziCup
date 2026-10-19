"""Four authorized fixed-source GETs preserve actual failing inputs outside Git, without a fix."""

import hashlib
import json
import os
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text

from ai_intel.infrastructure.network import NetworkPolicy, RequestDeadline, create_network_gateway
from ai_intel.infrastructure.settings import load_application_settings
from ai_intel.ingestion.source_catalog import CATALOG_SOURCES
from ai_intel.ingestion.source_jobs import CATALOG_CONTENT_TYPES, _fetch_catalog_page

RUN = Path(__file__).resolve().parent
OUTSIDE = Path("D:/dianzi-runtime-cache/01a13a70-858c-7d92-8070-0b2693ad7fc4/r06-integrated-live-1156/diagnostic-originals")
SHA = "1156b2ed6616e3a4297215c2893d2cbe633f5215"


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def main():
    assert not (RUN / "source_diagnosis.json").exists()
    OUTSIDE.mkdir(parents=True, exist_ok=True)
    started = now()
    settings = load_application_settings()
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"})
    with engine.connect() as connection:
        rows = list(connection.execute(text("select j.job_id,j.error_code,j.attempt_count,jp.payload from job_runs j join job_payloads jp on jp.job_id=j.job_id where j.job_type='collect_public_source_page' and j.status='blocked' order by j.created_at")).mappings())
        cursors = {row["source_id"]: row["cursor_json"] for row in connection.execute(text("select source_id,cursor_json from source_cursors where stream_kind='live'")).mappings()}
    engine.dispose()
    request_count = 0
    diagnosis = []
    for key in ("ollama_releases", "arxiv_security", "avid_community"):
        source = CATALOG_SOURCES[key]
        cursor = cursors.get(source.source_id, {})
        deadline = RequestDeadline(time.monotonic() + 12)
        gateway = create_network_gateway(NetworkPolicy(allowed_domains=(urlsplit(source.base_origin).hostname,), allowed_content_types=CATALOG_CONTENT_TYPES[key], total_timeout_seconds=12, dns_resolver=settings.dns_resolver), max_concurrent_requests=1)
        responses = []
        blocked = next(row for row in rows if json.loads(bytes(row["payload"]))["source_kind"] == key)
        entry = {"source_kind": key, "source_id": source.source_id, "blocked_job_id": blocked["job_id"], "original_error_code": blocked["error_code"], "cursor": cursor, "started_at": now()}

        def actual_fetch(url):
            nonlocal request_count
            assert request_count < 4
            request_count += 1
            observed = {"number": request_count, "source_kind": key, "requested_at": now(), "method": "GET", "url": url}
            try:
                result = gateway.fetch(url, max_redirect_hops=0, deadline=deadline)
                digest = hashlib.sha256(result.body).hexdigest()
                target = OUTSIDE / f"{key}-{request_count}-{digest}.body"
                target.write_bytes(result.body)
                observed.update({"completed_at": now(), "http_status": result.status_code, "content_type": result.content_type, "body_bytes": len(result.body), "raw_sha256": digest, "original_body_path": str(target), "redacted_headers": result.redacted_headers})
                return result
            except Exception as error:
                observed.update({"completed_at": now(), "error_type": type(error).__name__, "raw_body_available": False})
                raise
            finally:
                responses.append(observed)

        try:
            page, _ = _fetch_catalog_page(key, cursor, dns_resolver=settings.dns_resolver, fetcher=actual_fetch, poster=None, clock=lambda: datetime.now(UTC))
            entry["normalization"] = {"result": "accepted_on_diagnostic_reread", "document_count": len(page.documents), "next_cursor": page.next_cursor}
        except Exception as error:
            frames = traceback.extract_tb(error.__traceback__)
            entry["normalization"] = {"result": "reproduced_failure", "exception_type": type(error).__name__, "public_message": str(error)[:250] if type(error).__name__ in {"SourceCatalogError", "SourceDocumentError", "SourceAdapterError", "SourceFeedError", "ParsingError"} else "withheld; diagnosis agent can run frozen parser on original body", "trace_locations": [{"file": Path(frame.filename).name, "function": frame.name, "line": frame.lineno} for frame in frames]}
        entry.update({"ended_at": now(), "responses": responses})
        diagnosis.append(entry)
        (RUN / "source_diagnosis.json").write_text(json.dumps({"started_at": started, "ended_at": now(), "code_sha": SHA, "source_http_requests_attempted": request_count, "request_limit": 4, "no_retry_or_fixture": True, "actual_product_failure_inputs_are_not_overwritten": True, "diagnosis": diagnosis, "model_calls": 0, "paid_measurement_calls": 0}, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"source_http_requests_attempted": request_count, "diagnosis": [{"source_kind": entry["source_kind"], "normalization": entry["normalization"]["result"], "exception_type": entry["normalization"].get("exception_type"), "original_body_count": len(entry["responses"])} for entry in diagnosis]}))


if __name__ == "__main__":
    main()
